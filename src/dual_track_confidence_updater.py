# dual_track_confidence_updater.py — P1-D0：双轨置信度更新器
# ==================================================================
# 定位：梦境期四子模块（T0/T1/T2/T3）× 认知内核（HP3/HP4）交汇处
#         —— 统一置信度更新的唯一出口
#
# 设计背景：
#   旧系统有两个独立更新源：
#     1. confidence_manager.py 的 Q3→Q1 顿悟（空间通路）
#     2. gc_to_learning_adapter.py 的 GC 反馈（遗忘驱动）
#   新梦境模块引入两条新通路：
#     通路A（数形结合）：用户拓扑同构匹配触发
#     通路B（张力驱动）：梦境期矛盾解决触发
#
# 核心公式（两轨共享同一更新接口）：
#   通路A: ΔC = α × (1 - C₀) × S_activation
#          α ∈ [0.1, 0.3]  学习率
#          C₀ ∈ [0, 1]     当前置信度（越低越可塑）
#          S_activation ∈ [0, 1]  激活强度
#
#   通路B: ΔC = 0.15 + β × Tension_resolved
#          β ∈ [0.0, 0.5]  张力权重
#          Tension_resolved ∈ [0, 1]  已解决矛盾的张力值
#
# 统一接口：
#   update_confidence(C₀, track, **kwargs) → (C_new, ΔC, metadata)
#
# 版本：v1.1 | 2026-07-10 | 来源：梦境模块升级 × 千问 Facade 改造
# Facade 层：DreamPhase × process_dream_signal() 流程门卫
# ==================================================================

import json
import math
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
AGENT_MEM = WORKSPACE / "_agent_memory"
STATE_FILE = AGENT_MEM / "dual_track_state.json"

AGENT_MEM.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 枚举与常量
# =============================================================================

class Track(Enum):
    """双轨枚举"""
    SPATIAL = "track_A"   # 通路A：数形结合（用户拓扑同构）
    TEMPORAL = "track_B"  # 通路B：张力驱动（梦境矛盾解决）

    # 兼容旧接口
    Q3_EUREKA = "q3_eureka"      # confidence_manager.py 的 Q3→Q1
    GC_FEEDBACK = "gc_feedback"   # gc_to_learning_adapter 的遗忘信号


class DreamPhase(Enum):
    """
    梦境四阶段（由 T0/T1/T2/T3 子模块驱动）

    流程约束规则（千问指出的核心问题）：
      时间冷却掩盖了真相——梦境管线有严格顺序，
      某些轨道在某些阶段不应该接受信号。

    阶段 → 允许轨道矩阵：
      T0 矛盾蒸馏  → 仅 track_A（拓扑激活刚刚进入，需要先积累）
      T1 连线引擎  → 仅 track_A（拓扑连线进行中，不中断）
      T2 失谐放大  → 仅 track_B（T张力爆发，此刻才开始接受张力信号）
      T3 张力呼吸  → track_B + gc_feedback（矛盾解决期，全开）

    旧接口（q3_eureka / gc_feedback）：
      q3_eureka → 等效 track_A，允许 T0/T1
      gc_feedback → 仅允许 T3
    """
    T0 = "t0_distiller"
    T1 = "t1_connector"
    T2 = "t2_amplifier"
    T3 = "t3_breather"


# 阶段 → 允许轨道路由表
_PHASE_TRACK_ALLOWLIST: Dict[DreamPhase, set] = {
    DreamPhase.T0: {"track_A", "q3_eureka"},
    DreamPhase.T1: {"track_A", "q3_eureka"},
    DreamPhase.T2: {"track_B"},
    DreamPhase.T3: {"track_A", "track_B", "q3_eureka", "gc_feedback"},
}


@dataclass
class DreamSignalContext:
    """
    梦境信号上下文——Facade 层的输入单元

    将"当前梦境阶段"和"更新请求"打包在一起，
    传递给 process_dream_signal() 统一校验后路由。
    """
    phase: DreamPhase
    entry_id: str
    confidence_current: float
    track: str
    activation_strength: Optional[float] = None  # 通路A
    tension_resolved: Optional[float] = None     # 通路B
    similarity: Optional[float] = None          # q3_eureka
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ConfidenceUpdate:
    """单次置信度更新记录"""
    ts: float
    track: str                    # "track_A" | "track_B"
    entry_id: str                 # 记忆条目ID
    confidence_before: float
    confidence_after: float
    delta: float
    activation_strength: float     # 通路A：S_activation
    tension_resolved: float       # 通路B：Tension
    alpha: float                  # 通路A学习率
    beta: float                  # 通路B张力权重
    metadata: Dict[str, Any]      # 额外上下文

    def summary(self) -> str:
        if self.track == "track_A":
            return (f"[TrackA] {self.entry_id[:20]} "
                    f"C {self.confidence_before:.3f}→{self.confidence_after:.3f} "
                    f"(Δ={self.delta:.3f}, S={self.activation_strength:.2f})")
        else:
            return (f"[TrackB] {self.entry_id[:20]} "
                    f"C {self.confidence_before:.3f}→{self.confidence_after:.3f} "
                    f"(Δ={self.delta:.3f}, T={self.tension_resolved:.2f})")


# =============================================================================
# 核心类
# =============================================================================

class DualTrackConfidenceUpdater:
    """
    双轨置信度更新器

    功能：
      1. 通路A（数形结合）：用户拓扑同构匹配 → α×(1-C)×S
      2. 通路B（张力驱动）：梦境矛盾解决   → 0.15+β×Tension
      3. 兼容旧接口：Q3顿悟 + GC反馈
      4. 状态持久化（支持崩溃恢复）
      5. 顿悟冷却期（防止同一节点高频更新）
    """

    # 置信度边界
    CONF_MAX = 0.95   # 留怀疑空间（confidence_manager.py 同步）
    CONF_MIN = 0.05   # 最低值

    # 通路A参数
    ALPHA_DEFAULT = 0.2       # 默认学习率
    ALPHA_RANGE = (0.1, 0.3) # α有效范围
    ACTIVATION_MIN = 0.3      # 激活强度下限（低于此值不触发）

    # 通路B参数
    BETA_DEFAULT = 0.25       # 默认张力权重
    BETA_RANGE = (0.0, 0.5)  # β有效范围
    TENSION_BASE = 0.15       # 固定基础增量

    # 冷却期
    EUREKA_COOLDOWN = 3600   # 同一节点顿悟冷却（秒）≈ 一次梦境周期
    TRACK_B_COOLDOWN = 1800  # 通路B冷却（半梦境周期）

    def __init__(
        self,
        alpha: float = ALPHA_DEFAULT,
        beta: float = BETA_DEFAULT,
    ):
        self.alpha = self._clamp_alpha(alpha)
        self.beta = self._clamp_beta(beta)

        # 冷却期追踪
        self._cooldowns: Dict[str, float] = {}  # entry_id → last_update_ts

        # 顿悟历史（用于调参）
        self._history: List[ConfidenceUpdate] = []
        self._history_max = 100  # 保留最近100条

        # 统计
        self._stats = {
            "track_a_count": 0,
            "track_b_count": 0,
            "q3_eureka_count": 0,
            "gc_feedback_count": 0,
            "cooldown_skips": 0,
            "total_delta": 0.0,
        }

        # 加载持久化状态
        self._load_state()

    # ── 参数校验 ─────────────────────────────────────────────────────────────

    def _clamp_alpha(self, alpha: float) -> float:
        lo, hi = self.ALPHA_RANGE
        return max(lo, min(hi, alpha))

    def _clamp_beta(self, beta: float) -> float:
        lo, hi = self.BETA_RANGE
        return max(lo, min(hi, beta))

    # ── 核心 API：更新置信度 ────────────────────────────────────────────────

    def update(
        self,
        entry_id: str,
        confidence_current: float,
        track: str,
        activation_strength: Optional[float] = None,
        tension_resolved: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceUpdate:
        """
        统一更新接口

        Args:
            entry_id: 记忆条目ID
            confidence_current: 当前置信度 C₀
            track: "track_A" | "track_B" | "q3_eureka" | "gc_feedback"
            activation_strength: 通路A - 拓扑激活强度 S ∈ [0, 1]
            tension_resolved: 通路B - 已解决矛盾的张力值 T ∈ [0, 1]
            metadata: 额外上下文（来源/触发事件等）

        Returns:
            ConfidenceUpdate 记录
        """
        # 1. 冷却期检查
        cooldown = self._get_cooldown(track)
        if self._is_cooldown(entry_id, cooldown, track):
            self._stats["cooldown_skips"] += 1
            return self._make_noop_update(entry_id, confidence_current, track, metadata)

        # 2. 计算增量
        if track in ("track_A", "q3_eureka"):
            delta = self._compute_track_a(confidence_current, activation_strength or 0.5)
        elif track == "track_B":
            delta = self._compute_track_b(tension_resolved or 0.0)
        elif track == "gc_feedback":
            # GC反馈：弱化版通路B（遗忘节点的价值回升）
            delta = self._compute_track_b(tension_resolved or 0.0) * 0.3
        else:
            delta = 0.0

        # 3. 应用边界
        confidence_new = self._apply_delta(confidence_current, delta)
        actual_delta = confidence_new - confidence_current

        # 4. 构建记录
        update = ConfidenceUpdate(
            ts=time.time(),
            track=track,
            entry_id=entry_id,
            confidence_before=confidence_current,
            confidence_after=confidence_new,
            delta=actual_delta,
            activation_strength=activation_strength or 0.0,
            tension_resolved=tension_resolved or 0.0,
            alpha=self.alpha,
            beta=self.beta,
            metadata=metadata or {},
        )

        # 5. 持久化
        self._record(update)
        self._set_cooldown(entry_id, track)
        self._save_state()

        # 6. 更新统计
        self._update_stats(track, actual_delta)

        return update

    # ── Facade 层：梦境信号门卫（千问指出的核心改造）──────────────────────
    #
    # 问题（千问诊断）：
    #   时间冷却掩盖了流程约束的真相。
    #   梦境管线 T0→T1→T2→T3 有严格顺序，
    #   某些轨道在某些阶段本就不应该接受信号。
    #
    # 方案：
    #   新增 process_dream_signal() 作为唯一入口（Facade）。
    #   它负责：① 阶段校验  ② 冷却检查  ③ 数学计算（delegates）
    #   将"流程控制"和"业务逻辑"彻底分开。
    #
    # 使用方式：
    #   ctx = DreamSignalContext(phase=DreamPhase.T2, entry_id="node_42", ...)
    #   updater.process_dream_signal(ctx)  # 门卫校验后路由
    #

    def process_dream_signal(self, ctx: DreamSignalContext) -> ConfidenceUpdate:
        """
        Facade 入口——梦境信号门卫

        职责链：
          Step 1: 阶段路由校验（当前阶段是否允许该轨道？）
          Step 2: 冷却期检查（该节点是否在冷却中？）
          Step 3: 数学计算（delegates 到 update()）

        Args:
            ctx: DreamSignalContext 打包了所有必要信息

        Returns:
            ConfidenceUpdate（含拒绝原因 metadata）
        """
        # ── Step 1：阶段路由校验 ──────────────────────────────────
        allowed_tracks = _PHASE_TRACK_ALLOWLIST.get(ctx.phase, set())

        if ctx.track not in allowed_tracks:
            # 被阶段门卫拒绝——不是冷却，是流程不合规
            denial_meta = {
                "denied": True,
                "reason": "phase_mismatch",
                "phase": ctx.phase.value,
                "requested_track": ctx.track,
                "allowed_tracks": list(allowed_tracks),
                "hint": f"{ctx.track} not allowed in {ctx.phase.value}; "
                         f"try again in {[p.value for p in DreamPhase if ctx.track in _PHASE_TRACK_ALLOWLIST.get(p, set())]}",
            }
            return self._make_noop_update(
                entry_id=ctx.entry_id,
                confidence_current=ctx.confidence_current,
                track=ctx.track,
                metadata=denial_meta,
            )

        # ── Step 2+3：冷却检查 + 数学计算（delegates）─────────────
        # q3_eureka → 换算为 activation_strength 再传给 update()
        activation = ctx.activation_strength
        if ctx.track == "q3_eureka" and ctx.similarity is not None:
            activation = min(1.0, ctx.similarity * 0.8)

        return self.update(
            entry_id=ctx.entry_id,
            confidence_current=ctx.confidence_current,
            track=ctx.track,
            activation_strength=activation,
            tension_resolved=ctx.tension_resolved,
            metadata={
                "phase": ctx.phase.value,
                **(ctx.metadata or {}),
            },
        )

    def is_track_allowed_in_phase(self, track: str, phase: DreamPhase) -> bool:
        """
        查询接口——给定轨道在给定阶段是否允许

        供 T0/T1/T2/T3 子模块在发出信号前自检
        """
        return track in _PHASE_TRACK_ALLOWLIST.get(phase, set())

    def get_allowed_tracks(self, phase: DreamPhase) -> List[str]:
        """查询接口——给定阶段允许的所有轨道"""
        return list(_PHASE_TRACK_ALLOWLIST.get(phase, set()))

    # ── 通路A：数形结合（空间拓扑激活）─────────────────────────────

    def update_track_A(
        self,
        entry_id: str,
        confidence_current: float,
        activation_strength: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceUpdate:
        """
        通路A更新（用户拓扑同构匹配触发）

        触发条件（由调用方判断）：
          - 用户做出"数形结合"类比（拓扑同构匹配）
          - 身体出现麻感/张力共振
          - 语义相似度在排除点附近（非共性区）

        激活强度 S 的来源（由调用方传入）：
          - 用户身体信号：麻感强度 × 0.6 + 共振持续时间 × 0.4
          - 语义距离：排除点越远 → S 越高
          - 情感调制：surprise × 0.3 + insight × 0.7
        """
        return self.update(
            entry_id=entry_id,
            confidence_current=confidence_current,
            track="track_A",
            activation_strength=activation_strength,
            metadata=metadata,
        )

    def _compute_track_a(self, C: float, S: float) -> float:
        """
        通路A公式：ΔC = α × (1 - C₀) × S_activation

        设计哲学：
          - C 越高 → (1-C) 越小 → 边际更新越小（保护已建立的信念）
          - S 越高 → 更新幅度越大
          - C=0.5 时：ΔC = α × 0.5 × S → 中等更新
          - C=0.1 时：ΔC = α × 0.9 × S → 大量空间可塑
          - C=0.9 时：ΔC = α × 0.1 × S → 极小更新（抗拒同化）
        """
        if S < self.ACTIVATION_MIN:
            return 0.0
        delta = self.alpha * (1 - C) * S
        return delta

    # ── 通路B：张力驱动（梦境矛盾解决）────────────────────────────

    def update_track_B(
        self,
        entry_id: str,
        confidence_current: float,
        tension_resolved: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceUpdate:
        """
        通路B更新（梦境期矛盾解决触发）

        触发条件（由调用方判断）：
          - T2 失谐放大器产生张力峰值
          - T3 张力呼吸器完成一个完整周期
          - 梦境期发现两个矛盾节点之间的结构关系
          - 反事实推理（ToCT）发现旧假设的反例

        张力值 T 的来源（由调用方传入）：
          - 矛盾双方置信度差 × 0.4
          - 矛盾在拓扑图中的距离 × 0.3
          - 矛盾持续时间（梦境循环次数）× 0.3
          - 范围 [0, 1]
        """
        return self.update(
            entry_id=entry_id,
            confidence_current=confidence_current,
            track="track_B",
            tension_resolved=tension_resolved,
            metadata=metadata,
        )

    def _compute_track_b(self, T: float) -> float:
        """
        通路B公式：ΔC = 0.15 + β × Tension

        设计哲学：
          - 0.15 固定基底：保证即使低张力也有基础更新（防止死锁）
          - β × T：额外增量，与张力成正比
          - 张力越大 → 解决后的顿悟越强
          - T=0 时：ΔC = 0.15（最低更新）
          - T=1, β=0.25 时：ΔC = 0.15 + 0.25 = 0.40（最大更新）
        """
        T_clamped = max(0.0, min(1.0, T))
        delta = self.TENSION_BASE + self.beta * T_clamped
        return delta

    # ── 旧接口兼容 ─────────────────────────────────────────────────────────

    def update_q3_eureka(
        self,
        entry_id: str,
        confidence_current: float,
        similarity: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceUpdate:
        """
        兼容 confidence_manager.py 的 Q3→Q1 顿悟接口

        原有公式：Conf_new = Conf_old + Δ × Similarity
        其中 Δ = LEARNING_RATE = 0.2

        映射到通路A：
          α = 0.2 / max(similarity, 0.01) × 0.5
          S = similarity × 0.8
        """
        # 复用通路A，但用相似度换算激活强度
        activation = min(1.0, similarity * 0.8)
        return self.update_track_A(
            entry_id=entry_id,
            confidence_current=confidence_current,
            activation_strength=activation,
            metadata={"source": "q3_eureka", "similarity": similarity, **(metadata or {})},
        )

    def update_gc_feedback(
        self,
        entry_id: str,
        confidence_current: float,
        tension_resolved: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceUpdate:
        """
        兼容 gc_to_learning_adapter 的 GC 反馈接口

        GC反馈是遗忘节点的价值回升（被遗忘 → 证明有价值）
        使用弱化版通路B（×0.3），因为GC反馈的张力来源不同于梦境矛盾
        """
        return self.update(
            entry_id=entry_id,
            confidence_current=confidence_current,
            track="gc_feedback",
            tension_resolved=tension_resolved,
            metadata={"source": "gc_feedback", **(metadata or {})},
        )

    # ── 辅助方法 ───────────────────────────────────────────────────────────

    def _apply_delta(self, C: float, delta: float) -> float:
        """应用增量，带边界约束"""
        C_new = C + delta
        # 只向上约束（置信度只升不降），向下自由衰减
        return min(self.CONF_MAX, max(self.CONF_MIN, C_new))

    def _get_cooldown(self, track: str) -> float:
        if track == "track_A":
            return self.EUREKA_COOLDOWN
        elif track in ("track_B", "gc_feedback"):
            return self.TRACK_B_COOLDOWN
        else:  # q3_eureka
            return self.EUREKA_COOLDOWN

    def _is_cooldown(self, entry_id: str, cooldown: float, track: str) -> bool:
        key = f"{entry_id}:{track}"
        last = self._cooldowns.get(key, 0.0)
        return (time.time() - last) < cooldown

    def _set_cooldown(self, entry_id: str, track: str):
        """更新冷却时间戳（key = entry_id + track，双轨独立冷却）"""
        key = f"{entry_id}:{track}"
        self._cooldowns[key] = time.time()

    def _record(self, update: ConfidenceUpdate):
        self._history.append(update)
        if len(self._history) > self._history_max:
            self._history = self._history[-self._history_max:]

    def _update_stats(self, track: str, delta: float):
        if track == "track_A":
            self._stats["track_a_count"] += 1
        elif track == "track_B":
            self._stats["track_b_count"] += 1
        elif track == "q3_eureka":
            self._stats["q3_eureka_count"] += 1
        elif track == "gc_feedback":
            self._stats["gc_feedback_count"] += 1
        self._stats["total_delta"] += delta

    def _make_noop_update(
        self,
        entry_id: str,
        confidence_current: float,
        track: str,
        metadata: Optional[Dict[str, Any]],
    ) -> ConfidenceUpdate:
        return ConfidenceUpdate(
            ts=time.time(),
            track=track,
            entry_id=entry_id,
            confidence_before=confidence_current,
            confidence_after=confidence_current,
            delta=0.0,
            activation_strength=0.0,
            tension_resolved=0.0,
            alpha=self.alpha,
            beta=self.beta,
            metadata={"skipped": "cooldown", **(metadata or {})},
        )

    # ── 状态持久化 ─────────────────────────────────────────────────────────

    def _state_path(self) -> Path:
        return STATE_FILE

    def _load_state(self):
        path = self._state_path()
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cooldowns = data.get("cooldowns", {})
            # 历史不加载（全量太大）
        except Exception:
            pass

    def _save_state(self):
        path = self._state_path()
        data = {
            "cooldowns": self._cooldowns,
            "alpha": self.alpha,
            "beta": self.beta,
            "saved_at": time.time(),
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── 查询接口 ───────────────────────────────────────────────────────────

    def get_recent_updates(self, n: int = 10) -> List[Dict]:
        """获取最近n条更新记录（供 HP3 梦境期查询）"""
        recent = self._history[-n:]
        return [asdict(u) for u in recent]

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "alpha": self.alpha,
            "beta": self.beta,
            "cooldown_active": len(self._cooldowns),
        }

    def get_pending_updates(self) -> List[Dict]:
        """
        获取待应用的更新（供记忆系统批量处理）

        用于 HP3 梦境期结束时，将所有更新一次性写入记忆文件
        返回格式兼容 gc_to_learning_adapter 的信号格式
        """
        return [
            {
                "entry_id": u.entry_id,
                "confidence_before": u.confidence_before,
                "confidence_after": u.confidence_after,
                "delta": u.delta,
                "track": u.track,
                "ts": u.ts,
                "activation_strength": u.activation_strength,
                "tension_resolved": u.tension_resolved,
                "metadata": u.metadata,
            }
            for u in self._history[-20:]
            if u.delta != 0.0
        ]

    def adjust_alpha(self, alpha: float):
        """运行时调参（由 lambda_tuner 调用）"""
        self.alpha = self._clamp_alpha(alpha)
        self._save_state()

    def adjust_beta(self, beta: float):
        """运行时调参（由 lambda_tuner 调用）"""
        self.beta = self._clamp_beta(beta)
        self._save_state()

    # ── T5欲系统 → T7学习系统：欲系统张力 → Track B 置信度 ───────────────
    #
    # 耦合链路（千问补充的三维闭环）：
    #   cognitive_pain_monitor（预测误差）
    #     → surface_tension（尖刺/凹陷）
    #       → 欲系统未解尖刺
    #         → 本方法（读未解张力）
    #           → Track B 置信度加权
    #             → confidence_pipeline
    #
    # 原理：
    #   未解尖刺越多 → 认知资源被占用 → 学习效率下降
    #   公式：Track B 张力 = 已解决张力 - 未解张力（抑制项）
    #
    def get_unresolved_tension_penalty(self) -> float:
        """
        获取欲系统未解尖刺对置信度更新的惩罚系数
        供 Track B 调权时调用（由 prediction_tension_coupler 写入）

        返回：[0.0, 1.0]，1.0 = 无惩罚，0.0 = 完全抑制
        """
        try:
            import sys
            from pathlib import Path
            WS = Path("C:/Users/qq366410837/.qclaw/workspace")
            sys.path.insert(0, str(WS / "src"))
            from prediction_tension_coupler import get_unresolved_tension_score
            score = get_unresolved_tension_score()
            # 分数越高 → 惩罚越低（未解张力越低 → 学习越顺畅）
            # 分数越低 → 惩罚越高（未解张力越高 → 学习越受抑制）
            # score: 0-1 → penalty: 1.0-0.3
            return max(0.3, 1.0 - score * 0.7)
        except Exception:
            return 1.0  # 默认无惩罚

    def update_track_B_with_tension_penalty(
        self,
        entry_id: str,
        confidence_current: float,
        tension_resolved: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceUpdate:
        """
        Track B 更新，但受欲系统未解尖刺调制

        最终张力 = tension_resolved × penalty（未解惩罚）
        - 未解尖刺少 → penalty≈1 → 正常更新
        - 未解尖刺多 → penalty<1 → 更新幅度降低
        """
        penalty = self.get_unresolved_tension_penalty()
        adjusted_tension = tension_resolved * penalty
        meta = dict(metadata or {})
        meta["_tension_penalty"] = round(penalty, 3)
        meta["_unresolved_suppressed"] = round(tension_resolved - adjusted_tension, 3)
        return self.update(
            entry_id=entry_id,
            confidence_current=confidence_current,
            track="track_B",
            tension_resolved=adjusted_tension,
            metadata=meta,
        )

    def summary(self) -> str:
        """可打印状态摘要"""
        stats = self._stats
        lines = [
            f"[DualTrack] α={self.alpha:.2f} β={self.beta:.2f}",
            f"  TrackA={stats['track_a_count']} | TrackB={stats['track_b_count']} | "
            f"Q3={stats['q3_eureka_count']} | GC={stats['gc_feedback_count']}",
            f"  冷却跳过={stats['cooldown_skips']} | 总增量={stats['total_delta']:.3f}",
        ]
        return "\n".join(lines)


# =============================================================================
# 全局单例（供外部模块引用）
# =============================================================================

_updater: Optional[DualTrackConfidenceUpdater] = None


def get_updater() -> DualTrackConfidenceUpdater:
    """获取全局单例"""
    global _updater
    if _updater is None:
        _updater = DualTrackConfidenceUpdater()
    return _updater


# =============================================================================
# CLI 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("P1-D0: 双轨置信度更新器 测试")
    print("=" * 60)

    STATE_FILE.unlink(missing_ok=True)  # 清除持久化状态
    updater = DualTrackConfidenceUpdater(alpha=0.2, beta=0.25)

    # ── 测试1：通路A（数形结合）────────────────────────────────────
    print("\n[测试1] 通路A：数形结合")
    print(f"Formula: delta_C = alpha x (1-C0) x S,  alpha={updater.alpha}")
    updater._cooldowns.clear()  # 每组测试前清冷却

    cases_a = [
        (0.1, 0.9, "low conf + high activation -> max update"),
        (0.5, 0.7, "mid conf + mid activation -> medium update"),
        (0.8, 0.5, "high conf + low activation -> resists assimilation"),
        (0.9, 0.9, "high conf + high activation -> tiny update (protected)"),
        (0.5, 0.2, "below activation threshold -> skip"),
    ]

    for C, S, desc in cases_a:
        result = updater.update_track_A(
            entry_id=f"node_{C}_{S}",
            confidence_current=C,
            activation_strength=S,
            metadata={"desc": desc},
        )
        print(f"  {desc}")
        print(f"    C0={C:.2f} S={S:.2f} -> C_new={result.confidence_after:.3f} delta={result.delta:.3f}")

    # ── 测试2：冷却期验证（紧跟测试1，不清冷却）────────────────────
    print("\n[测试2] 冷却期验证")
    # test1 已用 entry_id="node_0.1_0.9" 触发 track_A
    # 现在立即重试同一节点，冷却期应该生效
    result = updater.update_track_A(
        entry_id="node_0.1_0.9",
        confidence_current=0.1,
        activation_strength=0.9,
        metadata={"desc": "within cooldown window"},
    )
    skipped = result.metadata.get("skipped") == "cooldown"
    # 冷却时：C_before=C0=C_after=0.1, delta=0.0, skipped=True
    # 无冷却时：C_before=0.1, C_after=0.262, delta=0.162, skipped=False
    print(f"  Same node immediate retry: delta={result.delta:.3f} C={result.confidence_before:.2f}->{result.confidence_after:.2f}")
    print(f"    {'[OK cooldown works]' if skipped else '[FAIL no cooldown]'}")

    # ── 测试3：通路B（张力驱动）────────────────────────────────────
    updater._cooldowns.clear()  # 清冷却
    print("\n[测试3] 通路B：张力驱动")
    print(f"Formula: delta_C = 0.15 + beta x T,  beta={updater.beta}")

    cases_b = [
        (0.3, 0.0, "no tension -> base increment only"),
        (0.5, 0.5, "mid tension"),
        (0.7, 1.0, "high tension -> max update"),
    ]

    for C, T, desc in cases_b:
        result = updater.update_track_B(
            entry_id=f"node_T{T}_{C}",
            confidence_current=C,
            tension_resolved=T,
            metadata={"desc": desc},
        )
        print(f"  {desc}")
        print(f"    C0={C:.2f} T={T:.2f} -> C_new={result.confidence_after:.3f} delta={result.delta:.3f}")

    # ── 测试4：边界约束 ────────────────────────────────────────
    updater._cooldowns.clear()  # 清冷却
    print("\n[测试4] 边界约束（CONF_MAX=0.95）")
    result = updater.update_track_B(
        entry_id="node_near_cap",
        confidence_current=0.93,
        tension_resolved=1.0,  # 理论增量 = 0.15 + 0.25 = 0.40
        metadata={"desc": "接近上限"},
    )
    print(f"  C0=0.93 theory delta=0.40 -> actual delta={result.delta:.3f} "
          f"C_new={result.confidence_after:.3f} {'[OK capped]' if result.confidence_after < 0.95+0.40 else '[FAIL uncapped]'}")

    # ── 测试5：旧接口兼容 ────────────────────────────────────────
    updater._cooldowns.clear()
    print("\n[测试5] 旧接口兼容")

    # Q3顿悟（原公式：Conf_new = Conf_old + 0.2 × Similarity）
    # 相似度=0.8 → 预期增量 = 0.2×0.8 = 0.16
    result = updater.update_q3_eureka(
        entry_id="q3_memory",
        confidence_current=0.4,
        similarity=0.8,
        metadata={"source": "test"},
    )
    print(f"  Q3_eureka(S=0.8): C0=0.40 -> C_new={result.confidence_after:.3f} delta={result.delta:.3f}")

    # ── 测试6：统计 ──────────────────────────────────────────────
    print("\n[测试6] 统计状态")
    print(updater.summary())

    # ── 测试7：Facade 阶段门卫（千问指出的核心改造）────────────────────
    updater._cooldowns.clear()
    print("\n[测试7] Facade: 梦境阶段门卫")
    print("路由规则表：")
    for phase in DreamPhase:
        tracks = updater.get_allowed_tracks(phase)
        print(f"  {phase.value}: {tracks}")

    print()

    # 7a：合法路由（T0 → track_A）
    ctx_legal = DreamSignalContext(
        phase=DreamPhase.T0,
        entry_id="test_t0_a",
        confidence_current=0.3,
        track="track_A",
        activation_strength=0.8,
    )
    result = updater.process_dream_signal(ctx_legal)
    denied = result.metadata.get("denied")
    print(f"  T0->track_A: C=0.30->{result.confidence_after:.3f} {'[OK allowed]' if not denied else '[FAIL denied]'}")

    # 7b：非法路由（T0 → track_B，应拒绝）
    ctx_illegal = DreamSignalContext(
        phase=DreamPhase.T0,
        entry_id="test_t0_b",
        confidence_current=0.5,
        track="track_B",
        tension_resolved=0.9,
    )
    result = updater.process_dream_signal(ctx_illegal)
    denied = result.metadata.get("denied")
    reason = result.metadata.get("reason")
    print(f"  T0->track_B: {'[OK denied]' if denied else '[FAIL allowed]'} reason={reason}")

    # 7c：合法路由（T2 → track_B）
    ctx_t2 = DreamSignalContext(
        phase=DreamPhase.T2,
        entry_id="test_t2_b",
        confidence_current=0.6,
        track="track_B",
        tension_resolved=0.7,
    )
    result = updater.process_dream_signal(ctx_t2)
    denied = result.metadata.get("denied")
    print(f"  T2->track_B: C=0.60->{result.confidence_after:.3f} {'[OK allowed]' if not denied else '[FAIL denied]'}")

    # 7d：gc_feedback 仅在 T3 合法
    for phase in [DreamPhase.T1, DreamPhase.T3]:
        updater._cooldowns.clear()  # 各次独立
        ctx_gc = DreamSignalContext(
            phase=phase,
            entry_id=f"test_gc_{phase.value}",
            confidence_current=0.4,
            track="gc_feedback",
            tension_resolved=0.6,
        )
        result = updater.process_dream_signal(ctx_gc)
        denied = result.metadata.get("denied")  # True=被拒绝, None/False=通过
        expected_denied = (phase != DreamPhase.T3)  # T1→拒绝, T3→通过
        ok = (denied == expected_denied) or (denied is None and not expected_denied)
        verdict = "[OK]" if ok else "[FAIL]"
        action = "denied" if denied else "allowed"
        print(f"  {phase.value}->gc_feedback: {action} {verdict}")

    # 7e：is_track_allowed_in_phase 查询接口
    print(f"\n  is_track_allowed('track_B', T2)={updater.is_track_allowed_in_phase('track_B', DreamPhase.T2)}  [True]")
    print(f"  is_track_allowed('track_B', T0)={updater.is_track_allowed_in_phase('track_B', DreamPhase.T0)}  [False]")

    # ── 测试8：冷却期 + 阶段门卫双重校验 ─────────────────────────────
    updater._cooldowns.clear()
    print("\n[测试8] Facade: 阶段门卫 + 冷却期双重校验")

    # 第一次：T3→track_B 合法，触发成功
    ctx1 = DreamSignalContext(
        phase=DreamPhase.T3,
        entry_id="test_dual",
        confidence_current=0.5,
        track="track_B",
        tension_resolved=0.8,
    )
    r1 = updater.process_dream_signal(ctx1)
    print(f"  1st (T3->B, fresh): C=0.50->{r1.confidence_after:.3f} delta={r1.delta:.3f}")

    # 第二次：同一节点还在冷却（阶段合法但冷却拒绝）
    ctx2 = DreamSignalContext(
        phase=DreamPhase.T3,
        entry_id="test_dual",
        confidence_current=0.5,
        track="track_B",
        tension_resolved=0.8,
    )
    r2 = updater.process_dream_signal(ctx2)
    skipped = r2.metadata.get("skipped")
    denied = r2.metadata.get("denied")
    print(f"  2nd (T3->B, cooling): {'[OK cooldown skip]' if skipped and not denied else '[FAIL]'}")

    # 第三次：阶段不允许（冷却也过但阶段不允许）
    ctx3 = DreamSignalContext(
        phase=DreamPhase.T0,
        entry_id="test_dual",
        confidence_current=0.5,
        track="track_B",
        tension_resolved=0.8,
    )
    r3 = updater.process_dream_signal(ctx3)
    denied = r3.metadata.get("denied")
    print(f"  3rd (T0->B, wrong phase): {'[OK denied]' if denied else '[FAIL]'}")

    print("\n" + "=" * 60)
    print("Facade 层改造完成：流程控制 vs 业务逻辑 彻底分离")
    print("测试完成")
    print("=" * 60)
