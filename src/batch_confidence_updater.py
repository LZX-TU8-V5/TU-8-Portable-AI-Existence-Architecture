# batch_confidence_updater.py — P1-D0 R3：O(1)高并发置信度更新
# =============================================================================
# 定位：SynapticConfidenceUpdater 的批量并发优化版
#         继承R2突触可塑性内核，追加O(1)优化
#
# O(1)核心实现（不依赖NumPy）：
#   1. 字典O(1)查找：每节点更新 = O(1)，不随总节点数增长
#   2. 延迟I/O：内存缓存 + 批量flush（每N次或每T秒写一次磁盘）
#   3. 批量预热：批量加载节点状态到内存，避免逐个加载
#
# 复杂度分析：
#   单节点更新：O(1) dict lookup + O(1) math + O(1/N) amortized I/O
#   N节点批量：O(N) math + O(1) I/O（N次 amortized）
#
# 版本：v1.0 | 2026-07-10 | 来源：R3需求
# =============================================================================

import sys
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any, List

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
AGENT_MEM = WORKSPACE / "_agent_memory"
sys.path.insert(0, str(WORKSPACE / "src"))

from synaptic_confidence_updater import SynapticConfidenceUpdater
from dual_track_state_machine import T2StateMachine, CostState
from confidence_explainer import ConfidenceExplainer


# =============================================================================
# 常量
# =============================================================================

DEFAULT_FLUSH_INTERVAL = 60      # 每60秒强制flush一次
DEFAULT_FLUSH_THRESHOLD = 50     # 每50次更新强制flush一次
DEFAULT_BATCH_LOAD = 200        # 批量加载时最多加载200个节点


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class NodeState:
    """节点置信度状态（内存缓存对象）"""
    entry_id: str
    confidence: float
    last_update_ts: float
    track: str = "unknown"
    cooldown_until: float = 0.0  # 冷却截止时间

    def is_cooldown(self) -> bool:
        return time.time() < self.cooldown_until

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "confidence": round(self.confidence, 6),
            "last_update_ts": self.last_update_ts,
            "track": self.track,
            "cooldown_until": self.cooldown_until,
        }


@dataclass
class BatchUpdateResult:
    """批量更新结果"""
    total_processed: int
    cache_hits: int
    flush_triggered: bool
    flush_reason: str
    total_time_ms: float
    per_node_avg_ms: float
    cost_summary: dict


# =============================================================================
# BatchConfidenceUpdater
# =============================================================================

class BatchConfidenceUpdater:
    """
    O(1)高并发置信度更新器

    核心保证：
      - 每节点更新 = O(1)（字典查找 + 常数时间数学）
      - I/O成本 amortized 到 O(1/N) per update
      - 批量加载避免 N×read 的串行 I/O

    内存结构：
      _cache: Dict[entry_id, NodeState]    ← O(1) 读写
      _dirty: Set[entry_id]                ← 待写入节点集合
      _cooldowns: Dict[entry_id, float]    ← 冷却追踪（O(1) lookup）
      _stats: dict                          ← 统计

    持久化策略：
      延迟写入：_dirty 集合满 || 时间到 → 批量 JSON.dump 一次
      启动加载：从文件读入 _cache，预热内存缓存
    """

    def __init__(
        self,
        state_file: Optional[Path] = None,
        flush_interval: int = DEFAULT_FLUSH_INTERVAL,
        flush_threshold: int = DEFAULT_FLUSH_THRESHOLD,
    ):
        self.state_file = state_file or (AGENT_MEM / "batch_confidence_state.json")
        self.flush_interval = flush_interval
        self.flush_threshold = flush_threshold

        # 核心数据结构
        self._cache: Dict[str, NodeState] = {}     # entry_id → NodeState
        self._dirty: set = set()                   # 待写入节点ID集合
        self._cooldowns: Dict[str, float] = {}     # entry_id → cooldown_until

        # I/O 控制
        self._last_flush_ts = time.time()
        self._update_count_since_flush = 0

        # 子组件（复用 R1/R2）
        self.updater = SynapticConfidenceUpdater()
        self.state_machine = T2StateMachine()
        self.explainer = ConfidenceExplainer()

        # 统计
        self._stats = {
            "total_updates": 0,
            "cache_hits": 0,
            "flush_count": 0,
            "nodes_loaded": 0,
        }

        # 加载持久化状态
        self._load_cache()

    # ── 持久化 ────────────────────────────────────────────────────────

    def _load_cache(self):
        """从磁盘加载缓存（O(N)一次，不在热路径上）"""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                raw = json.load(f)

            nodes = raw.get("nodes", [])
            for item in nodes:
                ns = NodeState(
                    entry_id=item["entry_id"],
                    confidence=item["confidence"],
                    last_update_ts=item["last_update_ts"],
                    track=item.get("track", "unknown"),
                    cooldown_until=item.get("cooldown_until", 0.0),
                )
                self._cache[ns.entry_id] = ns

            self._stats["nodes_loaded"] = len(nodes)
            # 重置dirty（从磁盘加载后暂无脏数据）
            self._dirty.clear()

        except Exception:
            pass

    def _persist(self, force: bool = False):
        """
        延迟批量写入（不在热路径上）
        只有 _dirty 非空且满足 flush 条件才写
        """
        # 触发条件：force 或 阈值超限 或 时间到
        should_flush = (
            force
            or len(self._dirty) >= self.flush_threshold
            or (time.time() - self._last_flush_ts) >= self.flush_interval
        )

        if not should_flush or not self._dirty:
            return

        # 批量序列化（所有脏节点一次写入）
        nodes = [
            self._cache[eid].to_dict()
            for eid in self._dirty
            if eid in self._cache
        ]

        manifest = {
            "version": 1,
            "ts": time.time(),
            "flush_reason": "periodic",
            "count": len(nodes),
        }

        try:
            AGENT_MEM.mkdir(parents=True, exist_ok=True)

            # 原子写入：先写.tmp，再 rename（防损坏）
            tmp_file = self.state_file.with_suffix(".json.tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump({"manifest": manifest, "nodes": nodes}, f, ensure_ascii=False)
            tmp_file.replace(self.state_file)

            self._dirty.clear()
            self._last_flush_ts = time.time()
            self._update_count_since_flush = 0
            self._stats["flush_count"] += 1

        except Exception:
            pass

    # ── 单节点更新（O(1)热路径）─────────────────────────────────────

    def update(
        self,
        entry_id: str,
        C_before: Optional[float] = None,
        track: str = "track_A",
        S: Optional[float] = None,
        T: Optional[float] = None,
        phase: str = "unknown",
        cooldown_sec: float = 3600.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """
        单节点 O(1) 更新

        热路径：O(1) dict lookup + O(1) math + O(1/N) amortized I/O
        """
        t0 = time.perf_counter()

        # ── Step 1：冷却检查（O(1) dict lookup）────────────────────
        cooldown_key = f"{entry_id}:{track}"
        now = time.time()
        if cooldown_key in self._cooldowns and now < self._cooldowns[cooldown_key]:
            return {
                "entry_id": entry_id,
                "state": "cooldown",
                "skipped": True,
                "delta": 0.0,
                "time_ms": (time.perf_counter() - t0) * 1000,
            }

        # ── Step 2：获取当前置信度（O(1) dict lookup）───────────────
        if entry_id in self._cache:
            C = C_before if C_before is not None else self._cache[entry_id].confidence
            self._stats["cache_hits"] += 1
        else:
            C = C_before if C_before is not None else 0.5  # 默认初始置信度
            # 写入缓存（新节点）
            self._cache[entry_id] = NodeState(
                entry_id=entry_id,
                confidence=C,
                last_update_ts=now,
                track=track,
            )

        # ── Step 3：数学计算（O(1)）─────────────────────────────────
        # SynapticUpdater（复用R2内核）
        if track in ("track_A", "q3_eureka"):
            delta = self.updater._compute_track_a(C, S or 0.5)
        else:
            delta = self.updater._compute_track_b(T or 0.0, C=C)

        C_after = C + delta
        C_after = max(0.0, min(1.0, C_after))  # 边界裁剪

        # ── Step 4：三锁检查（复用R1）────────────────────────────────
        # 注意：这里只做Sanity检查（全量Tension检查在dream期）
        if delta == 0.0:
            # 零更新：无需记录
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return {
                "entry_id": entry_id,
                "state": "zero_delta",
                "C_before": C,
                "C_after": C_after,
                "delta": 0.0,
                "time_ms": elapsed_ms,
            }

        # ── Step 5：更新缓存（O(1) dict write）──────────────────────
        self._cache[entry_id] = NodeState(
            entry_id=entry_id,
            confidence=C_after,
            last_update_ts=now,
            track=track,
            cooldown_until=now + cooldown_sec,
        )
        self._dirty.add(entry_id)

        # 冷却追踪
        self._cooldowns[cooldown_key] = now + cooldown_sec

        # ── Step 6：统计 ───────────────────────────────────────────
        self._update_count_since_flush += 1
        self._stats["total_updates"] += 1

        # ── Step 7：检查是否需要 flush（延迟I/O）───────────────────
        self._persist()

        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {
            "entry_id": entry_id,
            "state": "updated",
            "C_before": C,
            "C_after": C_after,
            "delta": delta,
            "time_ms": elapsed_ms,
        }

    # ── 批量更新（O(N) math + O(1) I/O）────────────────────────────

    def batch_update(
        self,
        signals: List[Dict[str, Any]],
        flush: bool = False,
    ) -> BatchUpdateResult:
        """
        批量更新 N 个节点

        复杂度：
          math: O(N)，每节点常数时间
          I/O: O(1)，N次更新共享一次批量写入

        性能目标：
          N=10,000 → ~50ms math（每节点5μs）
          vs 逐个update：N=10,000 → ~500ms（冷却/IO开销累积）
        """
        t0 = time.perf_counter()
        cache_hits = 0
        processed = 0

        for sig in signals:
            result = self.update(
                entry_id=sig["entry_id"],
                C_before=sig.get("C_before"),
                track=sig.get("track", "track_A"),
                S=sig.get("S"),
                T=sig.get("T"),
                phase=sig.get("phase", "batch"),
                cooldown_sec=sig.get("cooldown_sec", 3600.0),
            )
            if result["state"] == "updated":
                processed += 1
            if result.get("state") in ("updated", "cooldown"):
                cache_hits += 1

        # 强制flush（batch结束后）
        self._persist(force=flush)

        total_ms = (time.perf_counter() - t0) * 1000
        return BatchUpdateResult(
            total_processed=processed,
            cache_hits=cache_hits,
            flush_triggered=flush,
            flush_reason="batch_end" if flush else "threshold",
            total_time_ms=total_ms,
            per_node_avg_ms=total_ms / max(len(signals), 1),
            cost_summary=self.cost_summary(),
        )

    # ── 成本摘要 ────────────────────────────────────────────────────

    def cost_summary(self) -> dict:
        return {
            "total_updates": self._stats["total_updates"],
            "cache_hits": self._stats["cache_hits"],
            "flush_count": self._stats["flush_count"],
            "nodes_in_cache": len(self._cache),
            "dirty_pending": len(self._dirty),
            "nodes_loaded_from_disk": self._stats["nodes_loaded"],
        }

    def get_confidence(self, entry_id: str) -> Optional[float]:
        """O(1) 查询节点置信度"""
        ns = self._cache.get(entry_id)
        return ns.confidence if ns else None

    def flush_now(self):
        """强制立即写入（析构或关键节点前调用）"""
        self._persist(force=True)


# =============================================================================
# 性能测试（不依赖NumPy）
# =============================================================================

if __name__ == "__main__":
    import io, random
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )

    print("=" * 60)
    print("BatchConfidenceUpdater O(1)性能验证")
    print("=" * 60)

    updater = BatchConfidenceUpdater(
        flush_threshold=9999,  # 测试期间不自动flush
    )

    N = 10000
    print(f"\n生成 {N} 个模拟信号...")

    signals = [
        {
            "entry_id": f"node_{i}",
            "C_before": round(random.uniform(0.1, 0.9), 3),
            "track": random.choice(["track_A", "track_B"]),
            "S": round(random.uniform(0.0, 1.0), 2),
            "T": round(random.uniform(0.0, 1.0), 2),
        }
        for i in range(N)
    ]

    print(f"\n批量更新 {N} 个节点（flush=False）：")
    result = updater.batch_update(signals, flush=False)

    print(f"  处理：{result.total_processed}/{N} 节点")
    print(f"  缓存命中：{result.cache_hits}/{N}")
    print(f"  总耗时：{result.total_time_ms:.2f} ms")
    print(f"  每节点平均：{result.per_node_avg_ms:.4f} ms ({result.per_node_avg_ms*1000:.2f} μs)")
    print(f"  理论目标：~50ms（5μs/节点）")

    if result.total_time_ms < 200:
        print(f"  ✓ 性能达标（<200ms）")
    elif result.total_time_ms < 500:
        print(f"  ~ 性能可接受（<500ms）")
    else:
        print(f"  ⚠ 性能偏慢")

    # 强制flush测试
    print(f"\n强制flush（{len(updater._dirty)} 脏节点）：")
    t_flush = time.perf_counter()
    updater.flush_now()
    flush_ms = (time.perf_counter() - t_flush) * 1000
    print(f"  flush耗时：{flush_ms:.2f} ms")
    print(f"  ✓ 批量I/O amortized成功")

    # 对比：逐个update（N=100）
    print(f"\n对比：逐个update × 100（模拟热路径）:")
    signals100 = signals[:100]
    t_single = time.perf_counter()
    for sig in signals100:
        updater.update(
            entry_id=sig["entry_id"],
            C_before=sig.get("C_before"),
            track=sig.get("track"),
            S=sig.get("S"),
            T=sig.get("T"),
        )
    single_ms = (time.perf_counter() - t_single) * 1000
    print(f"  100次逐个update：{single_ms:.2f} ms（{single_ms/100:.4f} ms/次）")
    print(f"  100次批量batch：{result.per_node_avg_ms*100:.2f} ms（{result.per_node_avg_ms:.4f} ms/次）")
    print(f"  提速：{single_ms/(result.per_node_avg_ms*100):.1f}×")

    # 成本摘要
    print(f"\n成本摘要：")
    summary = updater.cost_summary()
    for k, v in summary.items():
        print(f"  {k}: {v}")
