"""
src/dissonance_amplifier.py — P1-T2 失谐放大器
================================================
核心职责：故意放大矛盾，不给和谐解释，留下悬念缺口。

功能：
  1. 张力值计算：f(矛盾强度, 置信度差, 空间距离)
  2. 失谐悬挂：张力达阈值 → 停止输出文字 → 留下悬念缺口
  3. 梦境期触发：dream_consolidation 梦境期执行

失谐 ≠ 冲突。失谐 = 知道这里有问题，但不知道答案是什么。
给不出答案 = 诚实。强行给和谐答案 = 撒谎。

触发条件：
  - 梦境期 metabolic 阶段
  - 从 T0 矛盾蒸馏器读取张力节点
  - 从 T1 拓扑连线器读取跨区域桥

输出：
  - 失谐日志（追加）
  - 悬念缺口列表（供 T3 张力呼吸器使用）
"""

import json
import time
import math
from pathlib import Path
from datetime import datetime
from typing import Optional

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
LOG_FILE = WORKSPACE / "_agent_memory" / "dissonance_log.jsonl"
HANG_FILE = WORKSPACE / "_agent_memory" / "dissonance_hang_points.json"
STATE_FILE = WORKSPACE / "_agent_memory" / "dissonance_state.json"

# =============================================
# 张力计算
# =============================================

def compute_dissonance_score(
    tension: float,
    confidence_gap: float,
    spatial_distance: float = 0.0,
    coherence_deficit: float = 0.0,
) -> dict:
    """
    计算失谐值（放大后的张力）。

    参数：
      tension: T0 输出的原始张力（0.0-1.0）
      confidence_gap: 两端置信度之差（0.0-1.0）
      spatial_distance: 拓扑空间距离（0.0-1.0+，越大越远）
      coherence_deficit: 因果连贯性亏空（0.0-1.0）

    返回：
      {
        raw_tension: float,      # 原始张力
        amplified_tension: float, # 放大后张力
        amplification_factor: float, # 放大系数
        components: dict,          # 各分量
        dissonance_level: str,     # "low" | "medium" | "high" | "critical"
        hang_threshold: float,    # 悬挂阈值（达到此值则悬挂）
      }
    """
    # 放大函数：非对称——低张力轻微放大，高张力剧烈放大
    # 目的：不让小矛盾悄悄滑过，也不让大矛盾被压平
    amplification_factor = 1.0 + 2.5 * (tension ** 2) * (1.0 + confidence_gap)

    # 各分量加权
    components = {
        "tension_contribution": tension * 0.4,
        "confidence_gap_contribution": confidence_gap * 0.25,
        "spatial_distance_contribution": min(spatial_distance, 1.0) * 0.2,
        "coherence_deficit_contribution": coherence_deficit * 0.15,
    }

    raw_sum = sum(components.values())
    amplified_tension = raw_sum * amplification_factor
    amplified_tension = min(amplified_tension, 1.0)  # 上限1.0

    # 失谐等级
    if amplified_tension >= 0.8:
        level = "critical"
        hang_threshold = 0.8
    elif amplified_tension >= 0.6:
        level = "high"
        hang_threshold = 0.6
    elif amplified_tension >= 0.4:
        level = "medium"
        hang_threshold = 0.4
    else:
        level = "low"
        hang_threshold = 1.0  # 不悬挂

    return {
        "raw_tension": tension,
        "amplified_tension": amplified_tension,
        "amplification_factor": amplification_factor,
        "components": components,
        "dissonance_level": level,
        "hang_threshold": hang_threshold,
        "should_hang": amplified_tension >= hang_threshold,
    }


def compute_confidence_gap(node_a_conf: float, node_b_conf: float) -> float:
    """计算置信度差距"""
    return abs(node_a_conf - node_b_conf)


def compute_spatial_distance(
    pos_a: tuple[float, float, float],
    pos_b: tuple[float, float, float],
) -> float:
    """计算3D拓扑空间距离"""
    dx = pos_a[0] - pos_b[0]
    dy = pos_a[1] - pos_b[1]
    dz = pos_a[2] - pos_b[2]
    return math.sqrt(dx*dx + dy*dy + dz*dz)


# =============================================
# 失谐悬挂生成
# =============================================

class HangPoint:
    """
    悬念缺口：知道这里有问题，但不知道答案。
    不给和谐解释，只留下问题本身。
    """

    def __init__(
        self,
        hang_id: str,
        anchor_a: str,
        anchor_b: str,
        dissonance_score: float,
        dissonance_level: str,
        raw_tension: float,
        description: str,
        question_formulated: str,
        honest_answer_state: str = "unknown",  # "unknown" | "partially_known" | "being_explored"
        created_at: float | None = None,
    ):
        self.hang_id = hang_id
        self.anchor_a = anchor_a
        self.anchor_b = anchor_b
        self.dissonance_score = dissonance_score
        self.dissonance_level = dissonance_level
        self.raw_tension = raw_tension
        self.description = description
        self.question_formulated = question_formulated
        self.honest_answer_state = honest_answer_state
        self.created_at = created_at or time.time()
        self.resolved_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "hang_id": self.hang_id,
            "anchor_a": self.anchor_a,
            "anchor_b": self.anchor_b,
            "dissonance_score": self.dissonance_score,
            "dissonance_level": self.dissonance_level,
            "raw_tension": self.raw_tension,
            "description": self.description,
            "question_formulated": self.question_formulated,
            "honest_answer_state": self.honest_answer_state,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }

    def mark_resolved(self):
        self.resolved_at = time.time()
        self.honest_answer_state = "resolved"

    def mark_exploring(self):
        self.honest_answer_state = "being_explored"


class DissonanceAmplifier:
    def __init__(self):
        self._hang_points: dict[str, HangPoint] = {}
        self._counter = 0
        self._load()

    def _load(self):
        if HANG_FILE.exists():
            try:
                data = json.loads(HANG_FILE.read_text(encoding="utf-8"))
                for hdict in data.get("hang_points", []):
                    h = HangPoint(**hdict)
                    self._hang_points[h.hang_id] = h
                self._counter = data.get("_counter", 0)
            except Exception:
                self._counter = 0
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"dissonance_events": 0, "hang_points_created": 0, "hang_points_resolved": 0}

    def _save(self):
        HANG_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "hang_points": [h.to_dict() for h in self._hang_points.values()],
            "_counter": self._counter,
        }
        HANG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_state(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _next_id(self) -> str:
        self._counter += 1
        return f"HANG-{self._counter:04d}"

    def amplify(
        self,
        anchor_a_id: str,
        anchor_b_id: str,
        raw_tension: float,
        description: str,
        confidence_a: float = 0.5,
        confidence_b: float = 0.5,
        spatial_distance: float = 0.0,
        coherence_deficit: float = 0.0,
        question_formulated: str | None = None,
    ) -> HangPoint | None:
        """
        执行失谐放大，生成悬念缺口。

        返回：HangPoint（若 should_hang=True），否则 None
        """
        confidence_gap = compute_confidence_gap(confidence_a, confidence_b)
        score = compute_dissonance_score(
            tension=raw_tension,
            confidence_gap=confidence_gap,
            spatial_distance=spatial_distance,
            coherence_deficit=coherence_deficit,
        )

        self._state["dissonance_events"] = self._state.get("dissonance_events", 0) + 1

        if not score["should_hang"]:
            return None

        # 生成悬念问题（如果未提供）
        if question_formulated is None:
            question_formulated = self._formulate_question(
                anchor_a_id, anchor_b_id, description, score["dissonance_level"]
            )

        hang_id = self._next_id()
        hang = HangPoint(
            hang_id=hang_id,
            anchor_a=anchor_a_id,
            anchor_b=anchor_b_id,
            dissonance_score=score["amplified_tension"],
            dissonance_level=score["dissonance_level"],
            raw_tension=raw_tension,
            description=description,
            question_formulated=question_formulated,
        )
        self._hang_points[hang_id] = hang
        self._state["hang_points_created"] = self._state.get("hang_points_created", 0) + 1

        self._save()
        self._save_state()

        # 追加日志
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                **score,
                "hang_id": hang_id,
                "anchor_a": anchor_a_id,
                "anchor_b": anchor_b_id,
                "question": question_formulated,
                "ts": time.time(),
            }, ensure_ascii=False) + "\n")

        return hang

    def _formulate_question(
        self,
        anchor_a: str,
        anchor_b: str,
        description: str,
        level: str,
    ) -> str:
        """
        将张力描述转化为诚实的悬念问题。
        原则：不给答案，只呈现问题的结构。
        """
        if level == "critical":
            # 极端张力：直接承认不知道
            return (
                f"「{description}」——这是不是一个根本性的框架冲突，"
                f"而不是可以调和的表面矛盾？"
            )
        elif level == "high":
            return (
                f"「{description}」——"
                f"锚点 {anchor_a} 和 {anchor_b} 之间的高张力，"
                f"是否指向一个更深层的结构问题？"
            )
        else:
            return (
                f"「{description}」——"
                f"这两个视角之间存在张力，但暂时无法给出统一解释。暂时悬挂。"
            )

    def get_hang_points(
        self,
        level: str | None = None,
        unresolved_only: bool = True,
    ) -> list[dict]:
        """获取悬念缺口列表"""
        result = []
        for h in self._hang_points.values():
            if unresolved_only and h.resolved_at is not None:
                continue
            if level is not None and h.dissonance_level != level:
                continue
            result.append(h.to_dict())
        return sorted(result, key=lambda h: h["dissonance_score"], reverse=True)

    def resolve(self, hang_id: str, resolution: str) -> bool:
        """解决一个悬念缺口（必须提供真实答案，非和谐解释）"""
        if hang_id not in self._hang_points:
            return False
        h = self._hang_points[hang_id]
        h.mark_resolved()
        h.question_formulated += f"\n[RESOLVED: {resolution}]"
        self._state["hang_points_resolved"] = self._state.get("hang_points_resolved", 0) + 1
        self._save()
        self._save_state()

        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "event": "resolved",
                "hang_id": hang_id,
                "resolution": resolution,
                "ts": time.time(),
            }, ensure_ascii=False) + "\n")
        return True

    def get_summary(self) -> dict:
        all_h = list(self._hang_points.values())
        unresolved = [h for h in all_h if h.resolved_at is None]
        by_level = {}
        for h in unresolved:
            by_level.setdefault(h.dissonance_level, 0)
            by_level[h.dissonance_level] += 1
        return {
            "total": len(all_h),
            "unresolved": len(unresolved),
            "resolved": len(all_h) - len(unresolved),
            "by_level": by_level,
            "critical_count": len([h for h in unresolved if h.dissonance_level == "critical"]),
            "state": self._state,
        }


# =============================================
# 全局实例
# =============================================

_amplifier: DissonanceAmplifier | None = None


def get_amplifier() -> DissonanceAmplifier:
    global _amplifier
    if _amplifier is None:
        _amplifier = DissonanceAmplifier()
    return _amplifier


def amplify_tension_node(
    anchor_a_id: str,
    anchor_b_id: str,
    raw_tension: float,
    description: str,
    confidence_a: float = 0.5,
    confidence_b: float = 0.5,
    spatial_distance: float = 0.0,
    coherence_deficit: float = 0.0,
) -> HangPoint | None:
    """便捷入口：放大一个张力节点"""
    return get_amplifier().amplify(
        anchor_a_id=anchor_a_id,
        anchor_b_id=anchor_b_id,
        raw_tension=raw_tension,
        description=description,
        confidence_a=confidence_a,
        confidence_b=confidence_b,
        spatial_distance=spatial_distance,
        coherence_deficit=coherence_deficit,
    )


def get_pending_hangs(level: str | None = None) -> list[dict]:
    """获取未解决的悬念缺口"""
    return get_amplifier().get_hang_points(level=level, unresolved_only=True)


def resolve_hang(hang_id: str, resolution: str) -> bool:
    return get_amplifier().resolve(hang_id, resolution)


# =============================================
# CLI
# =============================================

if __name__ == "__main__":
    amp = get_amplifier()

    # 演示：从 T0 的张力节点生成失谐
    demo_tensions = [
        {
            "anchor_a": "anchor_cortex",
            "anchor_b": "anchor_time",
            "raw_tension": 0.81,
            "confidence_a": 0.9,
            "confidence_b": 0.3,
            "spatial_distance": 0.4,
            "description": "皮层节律断层 vs 时间锚点漂移：高频震荡 vs 低频漂移",
        },
        {
            "anchor_a": "anchor_learning",
            "anchor_b": "anchor_heritage",
            "raw_tension": 0.72,
            "confidence_a": 0.6,
            "confidence_b": 0.85,
            "spatial_distance": 0.6,
            "description": "gc反馈过强导致学习链震荡 vs 遗产系统强制继承",
        },
        {
            "anchor_a": "anchor_cortex",
            "anchor_b": "anchor_heritage",
            "raw_tension": 0.55,
            "confidence_a": 0.9,
            "confidence_b": 0.85,
            "spatial_distance": 0.3,
            "description": "节奏断层 vs 遗产稳定性：动态 vs 静态",
        },
    ]

    print("=== 失谐放大演示 ===\n")
    for t in demo_tensions:
        hang = amplify_tension_node(
            anchor_a_id=t["anchor_a"],
            anchor_b_id=t["anchor_b"],
            raw_tension=t["raw_tension"],
            description=t["description"],
            confidence_a=t.get("confidence_a", 0.5),
            confidence_b=t.get("confidence_b", 0.5),
            spatial_distance=t.get("spatial_distance", 0.0),
            coherence_deficit=t.get("coherence_deficit", 0.0),
        )
        if hang:
            print(f"【悬挂】{hang.hang_id} | {hang.dissonance_level} | score={hang.dissonance_score:.3f}")
            print(f"  原始张力: {hang.raw_tension:.2f}")
            print(f"  放大系数: {hang.dissonance_score / hang.raw_tension:.2f}x")
            print(f"  悬念问题: {hang.question_formulated}")
            print()
        else:
            print(f"【通过】{t['anchor_a']}↔{t['anchor_b']} (张力不足，不悬挂)\n")

    print("=== 失谐摘要 ===")
    summary = amp.get_summary()
    print(f"总事件: {summary['state']['dissonance_events']}")
    print(f"悬挂缺口: {summary['unresolved']} 个")
    print(f"  critical: {summary['critical_count']} 个")
    print(f"  by_level: {summary['by_level']}")
    print()
    print("=== 未解决悬念 ===")
    for h in get_pending_hangs():
        print(f"  {h['hang_id']} [{h['dissonance_level']}] {h['question_formulated'][:60]}")
