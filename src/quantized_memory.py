# -*- coding: utf-8 -*-
# 创作者: 李奥(金木蟾) | TU-8 v5
"""
quantized_memory.py — TU-8/Q8 热温记忆量化压缩

设计原则（对应 TODO.md Q8 说明）：
  热/温记忆 → 可逆数值量化（KIVI/AWQ 风格 INT8/INT4），有损可还原
  冷记忆   → 不可逆摘要 + Embedding 索引，不存原始向量

三层存储路径（与 tu8_memory.py 的 phase 对齐）：
  Hot   (phase=short)  → RAM，原始 float32，零压缩，微秒级访问
  Warm  (phase=dream)  → 磁盘 JSON，INT8 量化 embedding，十毫秒级访问
  Cold  (phase=long)   → 磁盘 JSON，只存文本 + embedding 索引（FAISS），
                          不存原始向量，检索走 BM25 + 向量索引双路

量化算法：
  INT8 对称量化：scale = max(|v|) / 127,  quantized = round(v / scale)
  INT4 对称量化：scale = max(|v|) / 7,    quantized = round(v / scale)
                      两个 INT4 打包成一个 uint8 存储
  反量化：v' = quantized * scale

版本: v1.0 | 2026-06-05 | TU-8/Q8
"""

import json
import math
import struct
import time
import logging
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Union
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("tu8.quantized_memory")

# =============================================================================
# 配置常量
# =============================================================================

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
QUANTIZED_DIR = WORKSPACE / "memory" / "quantized"
HOT_CACHE_MAX_ENTRIES = 200      # 热记忆 RAM 上限
WARM_DISK_SYNC_INTERVAL = 60     # 温记忆刷盘间隔（秒）
EMBEDDING_DIM = 1024             # 默认 embedding 维度（sentence-transformers all-MiniLM-L6-v2 = 384）
                                 # Ollama mxbai-embed-large = 1024

# =============================================================================
# 量化器
# =============================================================================

class VectorQuantizer:
    """Embedding 向量量化器（KIVI/AWQ 风格）

    支持三种模式：
      - fp32: 不量化，原样返回（热记忆）
      - int8:  对称量化，每向量一个 scale，压缩比 ~4x
      - int4:  对称量化，每向量一个 scale，两个 int4 打包成 1 字节，压缩比 ~8x
    """

    @staticmethod
    def quantize_int8(
        vec: Union[List[float], "np.ndarray"]
    ) -> Tuple[List[int], float]:
        """INT8 对称量化

        Args:
            vec: 输入向量（float32）

        Returns:
            (quantized: List[int], scale: float)
            quantized 值域 [-128, 127]，scale 用于反量化
        """
        v = np.asarray(vec, dtype=np.float32)
        max_val = float(np.max(np.abs(v)))
        if max_val < 1e-9:
            return [0] * len(v), 1.0
        scale = max_val / 127.0
        quantized = np.clip(np.round(v / scale), -128, 127).astype(np.int8)
        return quantized.tolist(), float(scale)

    @staticmethod
    def dequantize_int8(
        quantized: List[int],
        scale: float,
        dtype: str = "float32"
    ) -> "np.ndarray":
        """INT8 反量化"""
        q = np.asarray(quantized, dtype=np.int8)
        return (q.astype(dtype) * scale).astype(np.float32)

    @staticmethod
    def quantize_int4(
        vec: Union[List[float], "np.ndarray"]
    ) -> Tuple[bytes, float, int]:
        """INT4 对称量化（两个 int4 打包成 1 字节）

        Returns:
            (packed: bytes, scale: float, dim: int)
            packed 长度 = ceil(dim / 2)，每个字节存两个 int4
            int4 值域 [-8, 7]
        """
        v = np.asarray(vec, dtype=np.float32)
        dim = len(v)
        max_val = float(np.max(np.abs(v)))
        if max_val < 1e-9:
            return b"\x00" * math.ceil(dim / 2), 1.0, dim
        scale = max_val / 7.0
        clipped = np.clip(np.round(v / scale), -8, 7).astype(np.int8)

        # 打包：低 4 位 = clipped[i]，高 4 位 = clipped[i+1]
        packed = bytearray(math.ceil(dim / 2))
        for i in range(0, dim, 2):
            low = int(clipped[i]) & 0x0F
            high = (int(clipped[i + 1]) & 0x0F) << 4 if i + 1 < dim else 0
            packed[i // 2] = low | high
        return bytes(packed), float(scale), dim

    @staticmethod
    def dequantize_int4(
        packed: bytes,
        scale: float,
        dim: int,
        dtype: str = "float32"
    ) -> "np.ndarray":
        """INT4 反量化"""
        v = np.zeros(dim, dtype=np.int8)
        for i in range(0, dim, 2):
            byte = packed[i // 2]
            low = byte & 0x0F
            high = (byte >> 4) & 0x0F
            # 符号恢复：int4 是有符号的，0x0F = -1，需要转换成 int8
            v[i] = low if low < 8 else low - 16
            if i + 1 < dim:
                v[i + 1] = high if high < 8 else high - 16
        return (v.astype(dtype) * scale).astype(np.float32)

    @staticmethod
    def compute_mse(
        original: Union[List[float], "np.ndarray"],
        dequantized: "np.ndarray"
    ) -> float:
        """计算量化失真度（MSE，越小越好）"""
        o = np.asarray(original, dtype=np.float32)
        return float(np.mean((o - dequantized) ** 2))


# =============================================================================
# 量化记忆条目
# =============================================================================

@dataclass
class QuantizedMemoryEntry:
    """量化后的记忆条目（对应 tu8_memory.MemoryEntry 的存储扩展）

    热记忆：embedding_fp32 非空，embedding_q / q_scale 为空（不量化）
    温记忆：embedding_fp32 为空，embedding_q + q_scale + q_mode 非空（INT8/INT4）
    冷记忆：embedding_fp32 / embedding_q 均为空，只有 embedding_index_id（FAISS ID）
    """
    id: str
    content: str
    phase: str = "short"      # short=热 / dream=温 / long=冷

    # 原始向量（仅热记忆）
    embedding_fp32: Optional[List[float]] = None

    # 量化向量（温记忆）
    q_mode: Optional[str] = None      # "int8" / "int4" / None
    q_scale: float = 0.0
    q_dim: int = 0
    q_packed: Optional[bytes] = None   # int4: packed bytes; int8 不使用此字段
    q_int8_list: Optional[List[int]] = None  # int8: List[int]，JSON 友好

    # 冷记忆索引（FAISS ID，对应外部向量索引）
    embedding_index_id: Optional[int] = None

    # 元数据（从 MemoryEntry 复制关键字段）
    freq: float = 0.0
    rel: float = 0.0
    div: float = 0.0
    created_at: float = 0.0
    last_recalled_at: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    steelmarked: bool = False

    def to_dict(self) -> Dict:
        """序列化为 JSON 友好的 dict"""
        d = asdict(self)
        # bytes → hex 字符串（int4 用）
        if d["q_packed"] is not None:
            d["q_packed"] = self.q_packed.hex()
        # q_int8_list 直接 JSON 序列化（int8 用）
        if not hasattr(self, 'q_int8_list') or self.q_int8_list is None:
            d.pop("q_int8_list", None)
        else:
            d["q_int8_list"] = self.q_int8_list
        # embedding_fp32 太大，温/冷记忆不存
        if self.phase in ("dream", "long"):
            d["embedding_fp32"] = None
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "QuantizedMemoryEntry":
        """从 dict 还原"""
        if d.get("q_packed") and isinstance(d["q_packed"], str):
            d["q_packed"] = bytes.fromhex(d["q_packed"])
        # q_int8_list 直接恢复（JSON 里是 List[int]）
        if "q_int8_list" in d and d["q_int8_list"] is not None:
            d["q_int8_list"] = list(d["q_int8_list"])
        return cls(**d)

    def get_embedding(self) -> Optional["np.ndarray"]:
        """获取反量化后的 embedding（热/温记忆）"""
        if self.embedding_fp32 is not None:
            return np.asarray(self.embedding_fp32, dtype=np.float32)
        if self.q_mode == "int8" and hasattr(self, 'q_int8_list') and self.q_int8_list is not None:
            return VectorQuantizer.dequantize_int8(self.q_int8_list, self.q_scale, dtype="float32")
        if self.q_mode == "int4" and self.q_packed is not None:
            return VectorQuantizer.dequantize_int4(
                self.q_packed, self.q_scale, self.q_dim
            )
        return None


# =============================================================================
# 热记忆 Store（RAM，零量化）
# =============================================================================

class HotMemoryStore:
    """热记忆层 — RAM 缓存，原始 float32，LRU 淘汰"""

    def __init__(self, max_entries: int = HOT_CACHE_MAX_ENTRIES):
        self.max_entries = max_entries
        self._store: Dict[str, QuantizedMemoryEntry] = {}
        self._lru_order: List[str] = []
        self._lock = __import__("threading").Lock()

    def put(self, entry: QuantizedMemoryEntry):
        """写入热记忆（embedding_fp32 必须非空）"""
        with self._lock:
            if entry.embedding_fp32 is None:
                logger.warning(f"HotStore.put: {entry.id} 无 embedding_fp32，拒绝写入热层")
                return False
            self._store[entry.id] = entry
            self._touch(entry.id)
            self._evict_if_needed()
            return True

    def get(self, entry_id: str) -> Optional[QuantizedMemoryEntry]:
        with self._lock:
            if entry_id not in self._store:
                return None
            self._touch(entry_id)
            return self._store[entry_id]

    def search(
        self,
        query_vec: "np.ndarray",
        top_k: int = 5,
        tags_filter: Optional[List[str]] = None
    ) -> List[Tuple[QuantizedMemoryEntry, float]]:
        """暴力余弦相似度检索（热记忆池很小，直接遍历）"""
        with self._lock:
            results = []
            for e in self._store.values():
                if e.embedding_fp32 is None:
                    continue
                if tags_filter and not any(t in e.tags for t in tags_filter):
                    continue
                vec = np.asarray(e.embedding_fp32, dtype=np.float32)
                sim = self._cosine_similarity(query_vec, vec)
                results.append((e, sim))
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]

    def remove(self, entry_id: str):
        with self._lock:
            if entry_id in self._store:
                del self._store[entry_id]
            if entry_id in self._lru_order:
                self._lru_order.remove(entry_id)

    def _touch(self, entry_id: str):
        if entry_id in self._lru_order:
            self._lru_order.remove(entry_id)
        self._lru_order.append(entry_id)

    def _evict_if_needed(self):
        while len(self._store) > self.max_entries:
            eldest = self._lru_order.pop(0)
            logger.info(f"HotStore LRU 淘汰: {eldest}")
            del self._store[eldest]

    @staticmethod
    def _cosine_similarity(a: "np.ndarray", b: "np.ndarray") -> float:
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na < 1e-9 or nb < 1e-9:
            return 0.0
        return float(np.dot(a, b) / (na * nb))


# =============================================================================
# 温记忆 Store（磁盘，INT8/INT4 量化）
# =============================================================================

class WarmMemoryStore:
    """温记忆层 — 磁盘 JSON 存储，INT8/INT4 量化 embedding"""

    def __init__(self, base_dir: Union[str, Path] = None):
        self.base_dir = Path(base_dir) if base_dir else QUANTIZED_DIR / "warm"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # 内存索引（ID → 元数据，不含量化向量，lazy load）
        self._index: Dict[str, Dict] = {}
        self._load_index()

    def _index_file(self) -> Path:
        return self.base_dir / "index.json"

    def _entry_file(self, entry_id: str) -> Path:
        # 分桶：取 ID 前 2 字符
        bucket = entry_id[:2] if len(entry_id) >= 2 else "00"
        bucket_dir = self.base_dir / bucket
        bucket_dir.mkdir(exist_ok=True)
        return bucket_dir / f"{entry_id}.json"

    def _load_index(self):
        """加载轻量索引（不含量化向量，快速启动）"""
        idx_file = self._index_file()
        if idx_file.exists():
            try:
                with open(idx_file, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
                logger.info(f"WarmStore 索引加载: {len(self._index)} 条")
            except Exception as e:
                logger.error(f"WarmStore 索引加载失败: {e}")
                self._index = {}

    def _save_index(self):
        with open(self._index_file(), "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)

    def put(self, entry: QuantizedMemoryEntry):
        """写入温记忆（量化后存储到磁盘）"""
        if entry.phase != "dream":
            entry.phase = "dream"  # 强制对齐

        # 如果还有原始向量，先量化
        if entry.embedding_fp32 is not None and entry.q_mode is None:
            q_mode = "int8"  # 默认 INT8
            if entry.embedding_fp32:
                q_list, q_scale = VectorQuantizer.quantize_int8(entry.embedding_fp32)
                # int8: 存为 List[int]（JSON 友好），不用 bytes
                entry.q_mode = q_mode
                entry.q_scale = q_scale
                entry.q_dim = len(entry.embedding_fp32)
                entry.q_packed = None  # int8 不用 packed，用 q_int8_list
                entry.q_int8_list = q_list  # 新增字段
                entry.embedding_fp32 = None  # 释放原始向量

        # 写入磁盘
        entry_dict = entry.to_dict()
        # q_int8_list 可能很大，单独处理
        if "q_int8_list" in entry_dict:
            # 存到文件里，index 只存 metadata
            pass  # to_dict() 已处理

        out_path = self._entry_file(entry.id)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(entry_dict, f, ensure_ascii=False)

        # 更新索引
        self._index[entry.id] = {
            "id": entry.id,
            "phase": entry.phase,
            "q_mode": entry.q_mode,
            "tags": entry.tags,
            "created_at": entry.created_at,
            "steelmarked": entry.steelmarked,
            "file": str(out_path.relative_to(self.base_dir)),
        }
        self._save_index()
        logger.debug(f"WarmStore.put: {entry.id} ({entry.q_mode})")

    def get(self, entry_id: str) -> Optional[QuantizedMemoryEntry]:
        """从磁盘加载完整条目（含量化向量）"""
        entry_path = self._entry_file(entry_id)
        if not entry_path.exists():
            return None
        with open(entry_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return QuantizedMemoryEntry.from_dict(d)

    def get_embedding(self, entry_id: str) -> Optional["np.ndarray"]:
        """只获取反量化后的 embedding（不加载完整条目）"""
        entry = self.get(entry_id)
        if entry is None:
            return None
        return entry.get_embedding()

    def search(
        self,
        query_vec: "np.ndarray",
        top_k: int = 5,
        tags_filter: Optional[List[str]] = None
    ) -> List[Tuple[QuantizedMemoryEntry, float]]:
        """遍历索引，逐条加载并反量化后计算相似度"""
        results = []
        for eid in self._index:
            entry = self.get(eid)
            if entry is None:
                continue
            emb = entry.get_embedding()
            if emb is None:
                continue
            if tags_filter and not any(t in entry.tags for t in tags_filter):
                continue
            sim = HotMemoryStore._cosine_similarity(query_vec, emb)
            results.append((entry, sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def remove(self, entry_id: str):
        entry_path = self._entry_file(entry_id)
        if entry_path.exists():
            entry_path.unlink()
        if entry_id in self._index:
            del self._index[entry_id]
            self._save_index()


# =============================================================================
# 冷记忆 Store（磁盘，不可逆摘要 + Embedding 索引）
# =============================================================================

class ColdMemoryStore:
    """冷记忆层 — 只存文本摘要 + FAISS 索引 ID，不存原始向量

    设计：
      - 文本摘要：存在 memory/quantized/cold/{id}.json（不可逆压缩产物）
      - 向量索引：由外部 FAISS 索引管理（embedding_index_id 对应 FAISS 的 vector ID）
      - 检索：先 BM25（文本）→ 再用 embedding_index_id 从 FAISS 取向量做 rerank
    """

    def __init__(self, base_dir: Union[str, Path] = None):
        self.base_dir = Path(base_dir) if base_dir else QUANTIZED_DIR / "cold"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index: Dict[str, Dict] = {}
        self._load_index()

    def _index_file(self) -> Path:
        return self.base_dir / "index.json"

    def _entry_file(self, entry_id: str) -> Path:
        bucket = entry_id[:2] if len(entry_id) >= 2 else "00"
        bucket_dir = self.base_dir / bucket
        bucket_dir.mkdir(exist_ok=True)
        return bucket_dir / f"{entry_id}.json"

    def _load_index(self):
        idx_file = self._index_file()
        if idx_file.exists():
            try:
                with open(idx_file, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
                logger.info(f"ColdStore 索引加载: {len(self._index)} 条")
            except Exception as e:
                logger.error(f"ColdStore 索引加载失败: {e}")
                self._index = {}

    def _save_index(self):
        with open(self._index_file(), "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)

    def put(
        self,
        entry_id: str,
        content: str,
        embedding_index_id: Optional[int] = None,
        tags: Optional[List[str]] = None,
        created_at: float = 0.0,
        steelmarked: bool = False,
    ):
        """写入冷记忆（不可逆摘要，不存原始向量）"""
        entry_data = {
            "id": entry_id,
            "content": content,   # 已是 LCM/compaction 的不可逆摘要
            "embedding_index_id": embedding_index_id,  # FAISS ID（外部管理）
            "tags": tags or [],
            "created_at": created_at or time.time(),
            "steelmarked": steelmarked,
            "phase": "long",
        }
        out_path = self._entry_file(entry_id)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(entry_data, f, ensure_ascii=False)

        self._index[entry_id] = {
            "id": entry_id,
            "tags": tags or [],
            "created_at": entry_data["created_at"],
            "steelmarked": steelmarked,
            "embedding_index_id": embedding_index_id,
            "file": str(out_path.relative_to(self.base_dir)),
        }
        self._save_index()
        logger.debug(f"ColdStore.put: {entry_id} (index_id={embedding_index_id})")

    def get(self, entry_id: str) -> Optional[Dict]:
        """读取冷记忆条目（不含向量）"""
        entry_path = self._entry_file(entry_id)
        if not entry_path.exists():
            return None
        with open(entry_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def remove(self, entry_id: str):
        entry_path = self._entry_file(entry_id)
        if entry_path.exists():
            entry_path.unlink()
        if entry_id in self._index:
            del self._index[entry_id]
            self._save_index()

    def list_ids(self) -> List[str]:
        return list(self._index.keys())


# =============================================================================
# 统一引擎（与 tu8_memory.py 集成入口）
# =============================================================================

class QuantizedMemoryEngine:
    """TU-8 Q8 统一量化记忆引擎

    与 tu8_memory.py 的集成方式：
      - TU8MemoryEngine.store(entry) 时，根据 entry.phase 调用本引擎的 route_store()
      - TU8MemoryEngine.recall(query) 时，调用本引擎的 route_recall()
      - 热温记忆的 embedding 由外部提供（Ollama / sentence-transformers）
    """

    def __init__(
        self,
        workspace_dir: Union[str, Path] = None,
        embedding_dim: int = EMBEDDING_DIM,
    ):
        self.workspace_dir = Path(workspace_dir) if workspace_dir else WORKSPACE
        self.embedding_dim = embedding_dim

        self.hot = HotMemoryStore(max_entries=HOT_CACHE_MAX_ENTRIES)
        self.warm = WarmMemoryStore(base_dir=self.workspace_dir / "memory" / "quantized" / "warm")
        self.cold = ColdMemoryStore(base_dir=self.workspace_dir / "memory" / "quantized" / "cold")

        self._lock = __import__("threading").Lock()
        logger.info(f"QuantizedMemoryEngine 初始化完成 (dim={embedding_dim})")

    # ------------------------------------------------------------------
    # 存储路由（根据 phase 分发）
    # ------------------------------------------------------------------

    def route_store(
        self,
        entry_id: str,
        content: str,
        embedding: Optional[List[float]] = None,
        phase: str = "short",   # short/dream/long
        tags: Optional[List[str]] = None,
        steelmarked: bool = False,
        created_at: float = 0.0,
    ) -> str:
        """根据 phase 路由到热/温/冷存储

        Args:
            entry_id: 唯一 ID
            content: 记忆文本内容
            embedding: 原始 float32 向量（可选，热温记忆建议提供）
            phase: 记忆层级
            tags: 标签列表
            steelmarked: 是否钢印固化
            created_at: 创建时间戳

        Returns:
            phase: 实际存储的层级
        """
        with self._lock:
            if phase == "short":
                # 热记忆：存原始向量
                qe = QuantizedMemoryEntry(
                    id=entry_id,
                    content=content,
                    phase="short",
                    embedding_fp32=embedding,
                    tags=tags or [],
                    steelmarked=steelmarked,
                    created_at=created_at or time.time(),
                )
                self.hot.put(qe)
                logger.info(f"[Q8] 热记忆写入: {entry_id}")
                return "short"

            elif phase == "dream":
                # 温记忆：量化后存储
                qe = QuantizedMemoryEntry(
                    id=entry_id,
                    content=content,
                    phase="dream",
                    tags=tags or [],
                    steelmarked=steelmarked,
                    created_at=created_at or time.time(),
                )
                if embedding is not None:
                    # INT8 量化
                    q_list, q_scale = VectorQuantizer.quantize_int8(embedding)
                    qe.q_mode = "int8"
                    qe.q_scale = q_scale
                    qe.q_dim = len(embedding)
                    qe.q_int8_list = q_list  # JSON 序列化友好
                    # embedding_fp32 不存（已量化）
                # 写入磁盘
                self.warm.put(qe)
                logger.info(f"[Q8] 温记忆写入(INT8量化): {entry_id}, scale={qe.q_scale:.4f}")
                return "dream"

            else:  # long / 其他 → 冷记忆
                # 冷记忆：不存向量，只存文本 + embedding_index_id（由外部 FAISS 管理）
                self.cold.put(
                    entry_id=entry_id,
                    content=content,
                    embedding_index_id=None,  # FAISS ID 由调用方管理
                    tags=tags,
                    created_at=created_at,
                    steelmarked=steelmarked,
                )
                logger.info(f"[Q8] 冷记忆写入(不可逆): {entry_id}")
                return "long"

    # ------------------------------------------------------------------
    # 召回路由
    # ------------------------------------------------------------------

    def route_recall(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        phase_filter: Optional[str] = None,  # "short" / "dream" / "long"
    ) -> List[Tuple[str, str, float]]:
        """跨热/温/冷三层召回

        Returns:
            List of (entry_id, content, score)
        """
        query_vec = np.asarray(query_embedding, dtype=np.float32)
        results = []

        # 热记忆召回
        if phase_filter in (None, "short"):
            hot_results = self.hot.search(query_vec, top_k=top_k)
            for entry, sim in hot_results:
                results.append((entry.id, entry.content, sim))

        # 温记忆召回（反量化后计算相似度）
        if phase_filter in (None, "dream"):
            warm_results = self.warm.search(query_vec, top_k=top_k)
            for entry, sim in warm_results:
                results.append((entry.id, entry.content, sim))

        # 冷记忆召回（只有文本，需要外部 FAISS 做向量检索，这里只返回索引条目）
        if phase_filter in (None, "long"):
            # 冷记忆不支持直接向量召回（无本地向量），由调用方通过 FAISS 索引召回
            # 这里只返回文本内容（供 BM25 使用）
            pass

        # 按相似度排序，去重
        seen = set()
        deduped = []
        for eid, content, score in sorted(results, key=lambda x: x[2], reverse=True):
            if eid not in seen:
                seen.add(eid)
                deduped.append((eid, content, score))
        return deduped[:top_k]

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict:
        return {
            "hot_count": len(self.hot._store),
            "warm_count": len(self.warm._index),
            "cold_count": len(self.cold._index),
            "embedding_dim": self.embedding_dim,
        }


# =============================================================================
# CLI 自测
# =============================================================================

if __name__ == "__main__":
    import time

    print("=" * 60)
    print("QuantizedMemoryEngine v1.0 自测")
    print("=" * 60)

    engine = QuantizedMemoryEngine()

    # 1. 生成随机 embedding 测试向量（模拟 Ollama embedding API）
    dim = 1024
    dummy_embedding = list(np.random.randn(dim).astype(np.float32))

    # 2. 热记忆写入 + 召回测试
    print("\n[1] 热记忆测试 (short phase)...")
    engine.route_store(
        entry_id="test_hot_001",
# 创作者: 李奥(金木蟾) | TU-8 v5
        embedding=dummy_embedding,
        phase="short",
        tags=["identity", "seed"],
        steelmarked=True,
    )
    hot_stats = engine.get_stats()
    print(f"    热记忆条数: {hot_stats['hot_count']}")

    # 3. 温记忆写入（INT8 量化）+ 失真度测试
    print("\n[2] 温记忆测试 (dream phase, INT8 量化)...")
    engine.route_store(
        entry_id="test_warm_001",
        content="Q8 量化压缩模块设计完成",
        embedding=dummy_embedding,
        phase="dream",
        tags=["q8", "design"],
    )
    # 计算量化失真度
    q_list, q_scale = VectorQuantizer.quantize_int8(dummy_embedding)
    deq = VectorQuantizer.dequantize_int8(q_list, q_scale)
    mse_int8 = VectorQuantizer.compute_mse(dummy_embedding, deq)
    print(f"    INT8 量化 MSE: {mse_int8:.8f}")

    # 4. INT4 量化失真度对比
    print("\n[3] INT4 量化失真度测试...")
    packed, scale4, dim4 = VectorQuantizer.quantize_int4(dummy_embedding)
    deq4 = VectorQuantizer.dequantize_int4(packed, scale4, dim4)
    mse_int4 = VectorQuantizer.compute_mse(dummy_embedding, deq4)
    print(f"    INT4 量化 MSE: {mse_int4:.8f}")
    print(f"    压缩比: INT8~4x, INT4~8x")

    # 5. 冷记忆写入测试
    print("\n[4] 冷记忆测试 (long phase, 不可逆)...")
    engine.route_store(
        entry_id="test_cold_001",
        content="LCM 压缩摘要：讨论了 Q3 复盘模块和 Q4 冷启动注入的设计。",
        phase="long",
        tags=["lcm", "summary"],
    )
    cold_stats = engine.get_stats()
    print(f"    冷记忆条数: {cold_stats['cold_count']}")

    # 6. 统计汇总
    print("\n[5] 统计汇总:")
    stats = engine.get_stats()
    for k, v in stats.items():
        print(f"    {k}: {v}")

    print("\n" + "=" * 60)
    print("自测完成")
    print("=" * 60)
