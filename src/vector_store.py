"""
vector_store.py — 话题语义矩阵 Vector 存储后端 [H 级批次1, 2026-08-28 落地]

设计稿：docs/design/topic_matrix_impl_design_2026-08-28.md §5
职责：
  - 稠密向量持久化（纯 Python list 初版，零依赖本地，避免 numpy 环境缺失）
  - 编码委托现有 TFIDFEmbedder（src/cognitive_evaluator.py，128维本地）
  - 可插拔 Vectorizer：默认 TFIDFEmbedder；可选 sentence_transformers（缺失自动降级）

不引云向量库（违背本地优先铁律）。FAISS 仅外部引用，不自维护。
零第三方依赖（与 TFIDFEmbedder 同风格，纯标准库）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

WORKSPACE = Path(
    os.environ.get("QCLAW_WORKSPACE", r"C:\Users\qq366410837\.qclaw\workspace")
)
VECTOR_DIR = WORKSPACE / "memory" / "matrix_vectors"
META_FILE = VECTOR_DIR / "meta.json"

DEFAULT_DIM = 128


def _cosine(a: list[float], b: list[float]) -> float:
    """纯 Python 余弦相似度。"""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class Vectorizer:
    """编码委托层：默认复用 TFIDFEmbedder，可选 sentence_transformers。"""

    def __init__(self, dim: int = DEFAULT_DIM, backend: str = "tfidf"):
        self.dim = dim
        self.backend = backend
        self._impl = None
        self._load()

    def _load(self):
        if self.backend == "tfidf":
            try:
                from cognitive_evaluator import TFIDFEmbedder
                self._impl = TFIDFEmbedder(dimension=self.dim, use_hashing=True)
            except Exception as e:
                raise RuntimeError(f"[Vectorizer] TFIDFEmbedder 加载失败: {e}")
        elif self.backend == "sentence_transformers":
            try:
                from sentence_transformers import SentenceTransformer
                self._impl = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
                self.dim = self._impl.get_sentence_embedding_dimension()
            except Exception:
                from cognitive_evaluator import TFIDFEmbedder
                self._impl = TFIDFEmbedder(dimension=self.dim, use_hashing=True)
                self.backend = "tfidf"
        else:
            raise ValueError(f"未知 backend: {self.backend}")

    def encode(self, text: str) -> list[float]:
        return [float(x) for x in self._impl.encode(text)]

    def similarity(self, a: str, b: str) -> float:
        if hasattr(self._impl, "compute_similarity"):
            return float(self._impl.compute_similarity(a, b))
        return _cosine(self.encode(a), self.encode(b))


class VectorStore:
    """轻量向量存储（纯 Python，单线程 rebuild）。"""

    def __init__(self, dim: int = DEFAULT_DIM, backend: str = "tfidf"):
        self.dim = dim
        self.vectorizer = Vectorizer(dim=dim, backend=backend)
        VECTOR_DIR.mkdir(parents=True, exist_ok=True)
        self._event_ids: list[str] = []
        self._vectors: list[list[float]] = []
        self._load_meta()

    def _load_meta(self):
        if META_FILE.exists():
            m = json.loads(META_FILE.read_text(encoding="utf-8"))
            self._event_ids = m.get("event_ids", [])
            # 向量与 event_ids 同序持久化（纯 JSON，128维×数百事件体积可控）
            self._vectors = m.get("vectors", [None] * len(self._event_ids))

    def add(self, event_id: str, text: str) -> list[float]:
        vec = self.vectorizer.encode(text)
        if event_id in self._event_ids:
            idx = self._event_ids.index(event_id)
            self._vectors[idx] = vec
        else:
            self._event_ids.append(event_id)
            self._vectors.append(vec)
        self._persist_meta()
        return vec

    def query(self, text: str, top_k: int = 5) -> list[tuple[str, float]]:
        if not self._event_ids:
            return []
        q = self.vectorizer.encode(text)
        scored = []
        for eid, vec in zip(self._event_ids, self._vectors):
            if vec is None:
                continue
            scored.append((eid, _cosine(q, vec)))
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def rebuild(self):
        self._persist_meta()

    def _persist_meta(self):
        META_FILE.write_text(
            json.dumps({
                "dim": self.dim,
                "event_ids": self._event_ids,
                "vectors": self._vectors,
            }, ensure_ascii=False),
            encoding="utf-8",
        )


if __name__ == "__main__":
    vs = VectorStore(dim=128, backend="tfidf")
    vs.add("evt_1", "TU-8 架构设计与钢印机制")
    vs.add("evt_2", "苹果是七七喜欢的水果")
    vs.add("evt_3", "架构演化与代谢通道上行")
    print("query top:", vs.query("TU-8 架构演化"))
    print("sim:", vs.vectorizer.similarity("TU-8 架构设计", "架构演化与代谢通道"))
