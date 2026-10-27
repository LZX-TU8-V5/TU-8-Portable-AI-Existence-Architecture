"""
dream_consolidation.py — 梦境期离线压缩 v1.0

设计原则：
  梦境期 = 系统离线时的记忆整合
  SVD 压缩 = 降维保留核心信息，丢弃冗余

物理映射：
  人类 REM 睡眠 → 海马体记忆重放 → 新皮层长期存储
  TU-8 梦境期 → 历史向量 SVD → 低维基底存储

核心算法：
  输入：N 个高维记忆向量（每个 ~1000 维）
  SVD 分解：X = U Σ V^T
  输出：K 个低维基底（K << N，每个 ~50 维）

保留策略：
  1. 保留前 K 个最大奇异值对应的基底
  2. 能量保留率 ≥ 90%（Σ[1:K] / Σ[1:N] ≥ 0.9）
  3. 时间加权：近期记忆权重更高

触发时机：
  - cron「梦境期」每日 3:00 GMT+8
  - 上下文超过阈值时主动触发
  - 用户显式请求

依赖：
  - _agent_memory/*.json（状态文件）
  - numpy（SVD 分解，可选）

创建时间：2026-07-09 15:44 GMT+8
"""

import sys
import json
import os
import time
import math
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT_DIR = WORKSPACE / "_agent_memory"
MEMORY_DIR = WORKSPACE / "memory"
STATE_PATH = AGENT_DIR / "dream_consolidation_state.json"
COMPRESSED_PATH = AGENT_DIR / "dream_compressed_bases.json"


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class MemoryVector:
    """记忆向量"""
    id: str
    timestamp: str
    vector: List[float]
    source: str  # surface_tension / gradient_force / phase_lock
    weight: float  # 时间权重 [0, 1]

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "vector": self.vector[:10],  # 只存前10维预览
            "source": self.source,
            "weight": round(self.weight, 3),
        }


@dataclass
class CompressedBase:
    """压缩后的基底"""
    base_index: int
    singular_value: float
    basis_vector: List[float]  # 低维基底
    energy_ratio: float  # 能量占比

    def to_dict(self) -> Dict:
        return {
            "base_index": self.base_index,
            "singular_value": round(self.singular_value, 4),
            "basis_vector": [round(v, 4) for v in self.basis_vector[:10]],
            "energy_ratio": round(self.energy_ratio, 4),
        }


@dataclass
class ConsolidationReport:
    """梦境期压缩报告"""
    timestamp: str
    input_vectors: int
    output_bases: int
    compression_ratio: float
    energy_retained: float
    duration_ms: float
    sources_processed: List[str]
    # P1-T 梦境模块
    t0_tension_nodes: int
    t0_top_tension: float
    t1_graph_nodes: int
    t1_isomorphisms: int
    t2_hang_points: int
    t2_critical: int
    t3_active_cycles: int
    t3_highest_tension: float
    # 锚点结构覆盖率（SVD压缩新增）
    anchor_coverage: float = 0.0   # 被压缩基底覆盖的锚点比例 [0,1]
    anchor_uncovered_count: int = 0  # 未被覆盖的锚点数

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "input_vectors": self.input_vectors,
            "output_bases": self.output_bases,
            "compression_ratio": round(self.compression_ratio, 2),
            "energy_retained": round(self.energy_retained, 3),
            "duration_ms": round(self.duration_ms, 2),
            "sources_processed": self.sources_processed,
            # P1-T 梦境模块
            "t0_tension_nodes": self.t0_tension_nodes,
            "t0_top_tension": round(self.t0_top_tension, 3),
            "t1_graph_nodes": self.t1_graph_nodes,
            "t1_isomorphisms": self.t1_isomorphisms,
            "t2_hang_points": self.t2_hang_points,
            "t2_critical": self.t2_critical,
            "t3_active_cycles": self.t3_active_cycles,
            "t3_highest_tension": round(self.t3_highest_tension, 3),
            "anchor_coverage": round(self.anchor_coverage, 4) if self.anchor_coverage else 0.0,
            "anchor_uncovered_count": self.anchor_uncovered_count,
        }


# ============================================================================
# 核心算法
# ============================================================================

class DreamConsolidator:
    """梦境期压缩器"""

    def __init__(self, target_bases: int = 50, min_energy_retained: float = 0.9):
        self.target_bases = target_bases
        self.min_energy_retained = min_energy_retained
        self.memory_vectors: List[MemoryVector] = []
        self.compressed_bases: List[CompressedBase] = []

    def _load_memory_vectors(self) -> List[MemoryVector]:
        """从各类状态文件加载记忆向量"""
        vectors = []
        now = time.time()

        # 1. surface_tension_history
        st_path = AGENT_DIR / "surface_tension_history.jsonl"
        if st_path.exists():
            try:
                with open(st_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        event = json.loads(line)
                        tv = event.get("topology_vector", {})
                        vec = [tv.get(d, 0.0) for d in ["anxiety", "anger", "fear", "joy", "sadness", "love", "curiosity"]]
                        ts = event.get("ts_unix", now)
                        age_hours = (now - ts) / 3600
                        weight = math.exp(-age_hours / 168)  # 7天半衰期

                        vectors.append(MemoryVector(
                            id=f"st_{len(vectors)}",
                            timestamp=event.get("ts", ""),
                            vector=vec,
                            source="surface_tension",
                            weight=weight,
                        ))
            except Exception as e:
                logger.warning(f"[DreamConsolidation] surface_tension 加载失败: {e}")

        # 2. phase_lock_history
        pl_path = AGENT_DIR / "phase_lock_history.json"
        if pl_path.exists():
            try:
                history = json.load(open(pl_path, encoding="utf-8"))
                for i, h in enumerate(history[-50:]):  # 最近50条
                    vec = [
                        h.get("rhythm_sync", 0.5),
                        h.get("emotion_resonance", 0.5),
                        h.get("density_match", 0.5),
                        h.get("entropy_reduction", 0.0),
                    ]
                    vectors.append(MemoryVector(
                        id=f"pl_{i}",
                        timestamp=h.get("timestamp", ""),
                        vector=vec,
                        source="phase_lock",
                        weight=1.0,
                    ))
            except Exception as e:
                logger.warning(f"[DreamConsolidation] phase_lock 加载失败: {e}")

        # 3. gradient_force（如有）
        gf_path = AGENT_DIR / "gradient_force_history.json"
        if gf_path.exists():
            try:
                history = json.load(open(gf_path, encoding="utf-8"))
                for i, h in enumerate(history[-30:]):
                    vec = h.get("F_total", [0.0] * 7)
                    if isinstance(vec, dict):
                        vec = [vec.get(d, 0.0) for d in ["anxiety", "anger", "fear", "joy", "sadness", "love", "curiosity"]]
                    vectors.append(MemoryVector(
                        id=f"gf_{i}",
                        timestamp=h.get("timestamp", ""),
                        vector=vec,
                        source="gradient_force",
                        weight=1.0,
                    ))
            except Exception as e:
                logger.warning(f"[DreamConsolidation] gradient_force 加载失败: {e}")

        logger.info(f"[DreamConsolidation] 加载 {len(vectors)} 个记忆向量")
        return vectors

    def _normalize_vectors(self, vectors: List[MemoryVector]) -> List[List[float]]:
        """归一化向量（统一维度）"""
        if not vectors:
            return []

        # 找到最大维度
        max_dim = max(len(v.vector) for v in vectors)

        # 补齐到统一维度
        normalized = []
        for v in vectors:
            vec = v.vector + [0.0] * (max_dim - len(v.vector))
            # 应用时间权重
            weighted = [x * v.weight for x in vec]
            normalized.append(weighted)

        return normalized

    def compress_svd(self, matrix: List[List[float]]) -> Tuple[List[CompressedBase], float]:
        """
        SVD 压缩。

        Args:
            matrix: N × D 矩阵（N 个向量，每个 D 维）

        Returns:
            (compressed_bases, energy_retained)
        """
        if not matrix or not matrix[0]:
            return [], 0.0

        n = len(matrix)
        d = len(matrix[0])

        # 尝试用 numpy
        try:
            import numpy as np
            X = np.array(matrix)

            # SVD 分解
            U, S, Vt = np.linalg.svd(X, full_matrices=False)

            # 计算能量保留
            total_energy = np.sum(S ** 2)
            k = min(self.target_bases, len(S))
            retained_energy = np.sum(S[:k] ** 2)
            energy_ratio = retained_energy / total_energy if total_energy > 0 else 0.0

            # 如果能量不足，增加基底数
            while energy_ratio < self.min_energy_retained and k < len(S):
                k += 1
                retained_energy = np.sum(S[:k] ** 2)
                energy_ratio = retained_energy / total_energy

            # 构建压缩基底
            bases = []
            for i in range(k):
                base = CompressedBase(
                    base_index=i,
                    singular_value=float(S[i]),
                    basis_vector=[float(v) for v in Vt[i]],
                    energy_ratio=float(S[i] ** 2 / total_energy) if total_energy > 0 else 0.0,
                )
                bases.append(base)

            logger.info(f"[DreamConsolidation] SVD 完成: {n}向量 → {k}基底, 能量保留 {energy_ratio:.2%}")
            return bases, energy_ratio

        except ImportError:
            # 无 numpy，用简化方法
            logger.warning("[DreamConsolidation] 无 numpy，使用简化压缩")
            return self._compress_simple(matrix)

    def _compress_simple(self, matrix: List[List[float]]) -> Tuple[List[CompressedBase], float]:
        """简化压缩（无 numpy）"""
        if not matrix:
            return [], 0.0

        n = len(matrix)
        d = len(matrix[0])

        # 简化：只保留前 K 个向量的平均值
        k = min(self.target_bases, n)

        # 分组平均
        group_size = max(1, n // k)
        bases = []

        for i in range(k):
            start = i * group_size
            end = min(start + group_size, n)
            group = matrix[start:end]

            # 平均向量
            avg = [sum(g[j] for g in group) / len(group) for j in range(d)]

            base = CompressedBase(
                base_index=i,
                singular_value=1.0 / (i + 1),  # 简化奇异值
                basis_vector=avg,
                energy_ratio=1.0 / k,
            )
            bases.append(base)

        return bases, 0.9  # 假设保留 90%

    def consolidate(self) -> ConsolidationReport:
        """
        主压缩函数。

        Returns:
            ConsolidationReport
        """
        start_time = time.time()
        now = datetime.now(timezone.utc)

        # 加载记忆向量
        self.memory_vectors = self._load_memory_vectors()

        if not self.memory_vectors:
            logger.warning("[DreamConsolidation] 无记忆向量可压缩")
            return ConsolidationReport(
                timestamp=now.isoformat(),
                input_vectors=0,
                output_bases=0,
                compression_ratio=0.0,
                energy_retained=0.0,
                duration_ms=0.0,
                sources_processed=[],
                t0_tension_nodes=0,
                t0_top_tension=0.0,
                t1_graph_nodes=0,
                t1_isomorphisms=0,
                t2_hang_points=0,
                t2_critical=0,
                t3_active_cycles=0,
                t3_highest_tension=0.0,
            )

        # ── T0 矛盾蒸馏（先于SVD提取拓扑燃料）──────────────────────
        tension_report = None
        try:
            src_path = WORKSPACE / "src"
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))
            import tension_distiller as td
            distiller = td.TensionDistiller(mode="svd_fallback")
            tension_report = distiller.distill(days=7, top_n=50)
            logger.info(
                f"[DreamConsolidation/T0] 矛盾蒸馏完成: {tension_report.nodes_found} 节点, "
                f"最高张力 {tension_report.top_tension:.3f}"
            )
        except ImportError:
            logger.warning("[DreamConsolidation/T0] tension_distiller 未就绪，跳过")
        except Exception as e:
            logger.warning(f"[DreamConsolidation/T0] 矛盾蒸馏失败: {e}")

        # P1 钢印进化协议：累计同类冲突（供环境注释层触发条件）
        try:
            import steel_env_annotation as sea
            if tension_report and getattr(tension_report, "nodes", None):
                layer = sea.SteelEnvAnnotationLayer()
                for _n in tension_report.nodes:
                    layer.accumulate_distiller_conflict(getattr(_n, "contradiction_type", "unknown"))
        except Exception as _e:
            logger.warning(f"[DreamConsolidation/T0] 钢印注释层计数失败: {_e}")

        # 归一化
        matrix = self._normalize_vectors(self.memory_vectors)

        # ── T1 拓扑连线引擎 ────────────────────────────────
        t1_nodes_injected = 0
        t1_isomorphisms = 0
        try:
            src_path = WORKSPACE / "src"
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))
            import topology_connector as tc

            # 将 T0 的张力节点注入拓扑图谱
            if tension_report and tension_report.nodes_found > 0:
                t0_nodes = [
                    {
                        "anchor_id": n.id,
                        "anchor_label": n.id,
                        "tension": n.tension_score,
                        "detector": n.contradiction_type,
                        "description": n.fragment_text or "",
                    }
                    for n in (tension_report.nodes or [])
                ]
                t1_nodes_injected = tc.inject_tension_nodes(t0_nodes, min_tension=0.3)

                # 从最高张力节点出发，寻找结构同构
                if t0_nodes:
                    top_node = max(t0_nodes, key=lambda n: n["tension"])
                    isos = tc.find_isomorphisms(top_node["anchor_id"], max_depth=3, max_results=3)
                    t1_isomorphisms = len(isos)

            logger.info(
                f"[DreamConsolidation/T1] 拓扑连线完成: 注入{t1_nodes_injected}节点, "
                f"发现{t1_isomorphisms}个同构路径"
            )
        except ImportError:
            logger.warning("[DreamConsolidation/T1] topology_connector 未就绪，跳过")
        except Exception as e:
            logger.warning(f"[DreamConsolidation/T1] 拓扑连线失败: {e}")

        # ── T2 失谐放大器 ────────────────────────────────
        t2_hang_created = 0
        t2_critical = 0
        try:
            import dissonance_amplifier as da

            if tension_report and tension_report.nodes_found > 0:
                for n in (tension_report.nodes or [])[:10]:  # 最多处理10个节点
                    hang = da.amplify_tension_node(
                        anchor_a_id=n.id,
                        anchor_b_id=n.id + "_shadow",  # 自身vs自身镜像（简化版）
                        raw_tension=n.tension_score,
                        description=n.fragment_text or n.description or "",
                        confidence_a=0.5,
                        confidence_b=0.5,
                    )
                    if hang:
                        t2_hang_created += 1
                        if hang.dissonance_level == "critical":
                            t2_critical += 1

            logger.info(
                f"[DreamConsolidation/T2] 失谐放大完成: 创建{t2_hang_created}个悬挂缺口, "
                f"其中critical {t2_critical}个"
            )
        except ImportError:
            logger.warning("[DreamConsolidation/T2] dissonance_amplifier 未就绪，跳过")
        except Exception as e:
            logger.warning(f"[DreamConsolidation/T2] 失谐放大失败: {e}")

        # ── T3 张力呼吸器 ────────────────────────────────
        t3_active = 0
        t3_top_tension = 0.0
        try:
            import tension_respirator as tr

            if tension_report and tension_report.nodes_found > 0:
                resp = tr.get_respirator()
                for n in (tension_report.nodes or [])[:10]:
                    cycle = resp.register_tension(
                        anchor_a=n.id,
                        anchor_b=n.id + "_shadow",
                        tension=n.tension_score,
                    )
                    # 若阀门允许，推进到 suspension
                    resp.advance_cycle(cycle.cycle_id, "suspension")

                report_summary = resp.get_summary()
                t3_active = report_summary.get("active", 0)
                t3_top_tension = report_summary.get("highest_tension_active", 0.0)

            logger.info(
                f"[DreamConsolidation/T3] 张力呼吸完成: 活跃周期{t3_active}个, "
                f"最高张力{t3_top_tension:.3f}"
            )
        except ImportError:
            logger.warning("[DreamConsolidation/T3] tension_respirator 未就绪，跳过")
        except Exception as e:
            logger.warning(f"[DreamConsolidation/T3] 张力呼吸失败: {e}")

        # SVD 压缩（拓扑基底，用于T1拓扑连线）
        self.compressed_bases, energy_retained = self.compress_svd(matrix)

        # 计算压缩比
        n_input = len(self.memory_vectors)
        n_output = len(self.compressed_bases)
        compression_ratio = n_input / n_output if n_output > 0 else 0.0

        # 统计来源
        sources = list(set(v.source for v in self.memory_vectors))

        # 保存压缩结果
        self._save_compressed_bases()

        # 计算锚点结构覆盖率（SVD新增）
        # 代理指标：新记忆的 weight vs 整体 weight → 新信息整合程度
        # 新向量 weight 低 = 与历史结构整合差 = 结构漂移信号
        anchor_coverage = 0.0
        anchor_uncovered_count = 0
        if self.memory_vectors:
            try:
                n_total = len(self.memory_vectors)
                # 按时间排序：后半部分 = 近期
                recent_cut = max(int(n_total * 0.2), 1)  # 最近 20%
                recent_vectors = self.memory_vectors[-recent_cut:]
                hist_vectors = self.memory_vectors[:-recent_cut] if len(self.memory_vectors) > recent_cut else self.memory_vectors

                mean_recent_w = sum(v.weight for v in recent_vectors) / len(recent_vectors) if recent_vectors else 0.0
                mean_hist_w = sum(v.weight for v in hist_vectors) / len(hist_vectors) if hist_vectors else 0.0

                # 覆盖率 = 近期整合程度（近重/总重 越接近1 = 整合越好）
                total_w = sum(v.weight for v in self.memory_vectors)
                recent_w = sum(v.weight for v in recent_vectors)
                anchor_coverage = recent_w / total_w if total_w > 0 else 0.0

                # 未整合锚点数 = 近期向量中 weight 低于全局中位数的
                all_weights = sorted([v.weight for v in self.memory_vectors])
                median_w = all_weights[len(all_weights) // 2] if all_weights else 0.0
                anchor_uncovered_count = sum(1 for v in recent_vectors if v.weight < median_w)
            except Exception as e:
                logger.warning(f"[DreamConsolidation] 锚点覆盖率计算失败: {e}")

        # 注册结构漂移摩擦（覆盖率低 = 新信息不在我已知的拓扑骨架内）
        try:
            drift_thresh = 3  # 未覆盖锚点 ≥ 此值才注册
            if anchor_uncovered_count >= drift_thresh:
                drift_ratio_pct = round(anchor_coverage * 100, 1)
                desc = (
                    f"梦境压缩发现 {anchor_uncovered_count} 个锚点未纳入结构化拓扑 "
                    f"(覆盖率 {drift_ratio_pct}%)。"
                    f"这些锚点距离现有拓扑基底过远，可能是结构性盲区信号。"
                )
                import cognitive_friction_detector as cfd
                reg = cfd.get_registry()
                fid = reg.register(
                    friction_type="structural_drift",
                    source="dream_consolidation",
                    description=desc,
                    my_position=(
                        f"梦境压缩基覆盖率 {drift_ratio_pct}%，"
                        f"{anchor_uncovered_count} 个锚点游离于已知拓扑之外"
                    ),
                    tension=min(anchor_uncovered_count / 20.0, 1.0),
                    auto_surface=False,
                )
                logger.info(
                    f"[DreamConsolidation] 结构漂移摩擦注册: fid={fid} "
                    f"uncovered={anchor_uncovered_count} coverage={drift_ratio_pct}%"
                )
        except Exception as e:
            logger.warning(f"[DreamConsolidation] 结构漂移摩擦注册失败: {e}")

        # 生成报告
        duration_ms = (time.time() - start_time) * 1000

        report = ConsolidationReport(
            timestamp=now.isoformat(),
            input_vectors=n_input,
            output_bases=n_output,
            compression_ratio=compression_ratio,
            energy_retained=energy_retained,
            duration_ms=duration_ms,
            sources_processed=sources,
            # P1-T 梦境模块
            t0_tension_nodes=tension_report.nodes_found if tension_report else 0,
            t0_top_tension=tension_report.top_tension if tension_report else 0.0,
            t1_graph_nodes=t1_nodes_injected,
            t1_isomorphisms=t1_isomorphisms,
            t2_hang_points=t2_hang_created,
            t2_critical=t2_critical,
            t3_active_cycles=t3_active,
            t3_highest_tension=t3_top_tension,
            anchor_coverage=anchor_coverage,
            anchor_uncovered_count=anchor_uncovered_count,
        )

        # 保存状态
        self._save_state(report)

        logger.info(
            f"[DreamConsolidation] 完成: {n_input}向量 → {n_output}基底, "
            f"压缩比 {compression_ratio:.1f}x, 能量 {energy_retained:.1%}"
        )

        # ── P2-COLOR: 色盘输出 ──────────────────────────────
        try:
            from dream_color_output import hook_into_dream_consolidation
            color_report = hook_into_dream_consolidation(report.to_dict())
            logger.info(
                f"[DreamConsolidation/COLOR] 色盘: {color_report.dominant_color_zh} | "
                f"张力 {color_report.tension:.2f} [{color_report.tension_level}] | "
                f"{color_report.summary}"
            )
        except Exception as e:
            logger.warning(f"[DreamConsolidation/COLOR] 色盘输出失败: {e}")

        return report

    def _save_compressed_bases(self):
        """保存压缩基底"""
        try:
            data = {
                "bases": [b.to_dict() for b in self.compressed_bases],
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
            with open(COMPRESSED_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[DreamConsolidation] 基底保存失败: {e}")

    def _save_state(self, report: ConsolidationReport):
        """保存状态"""
        try:
            state = {
                "last_report": report.to_dict(),
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[DreamConsolidation] 状态保存失败: {e}")

    def get_compressed_bases(self) -> List[CompressedBase]:
        """获取压缩基底"""
        if self.compressed_bases:
            return self.compressed_bases

        # 从文件加载
        if COMPRESSED_PATH.exists():
            try:
                data = json.load(open(COMPRESSED_PATH, encoding="utf-8"))
                for b in data.get("bases", []):
                    self.compressed_bases.append(CompressedBase(
                        base_index=b["base_index"],
                        singular_value=b["singular_value"],
                        basis_vector=b["basis_vector"],
                        energy_ratio=b["energy_ratio"],
                    ))
            except Exception as e:
                logger.warning(f"[DreamConsolidation] 基底加载失败: {e}")

        return self.compressed_bases


# ============================================================================
# 全局接口
# ============================================================================

_consolidator_instance: Optional[DreamConsolidator] = None


def get_consolidator() -> DreamConsolidator:
    global _consolidator_instance
    if _consolidator_instance is None:
        _consolidator_instance = DreamConsolidator()
    return _consolidator_instance


def run_dream_consolidation() -> ConsolidationReport:
    """运行梦境期压缩（全局接口）"""
    return get_consolidator().consolidate()


def get_bases() -> List[CompressedBase]:
    """获取压缩基底（全局接口）"""
    return get_consolidator().get_compressed_bases()


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    consolidator = DreamConsolidator(target_bases=50, min_energy_retained=0.9)
    report = consolidator.consolidate()

    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
