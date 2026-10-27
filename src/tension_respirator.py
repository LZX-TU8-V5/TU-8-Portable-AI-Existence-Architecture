"""
src/tension_respirator.py — P1-T3 张力呼吸器
==============================================
核心职责：顶层节律编排器，统领 T0/T1/T2 的执行节奏。

节律四拍：
  ① 张力激活（Activation）  — T0 检测到张力节点
  ② 梦境期悬挂（Suspension）— T2 生成悬念缺口，等待
  ③ 通路B演化（Evolution）   — B通路置信度演化（双轨置信度更新）
  ④ 归位复位（Reset）       — 解决悬念 or 归档

用户节律阀门：
  - posture_zone=critical/red → 阀门关闭（不输出，不触发演化）
  - posture_zone=warning/orange → 低频放行（仅检测，不深度演化）
  - posture_zone=green → 全速运行

目的：
  - 防止 TU-8 在张力很高时强行输出（给自己和用户造成压力）
  - 确保张力节点有足够的"消化时间"
  - 诚实呈现：知道就是知道，不知道就是不知道
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Literal

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
STATE_FILE = WORKSPACE / "_agent_memory" / "respiration_state.json"
LOG_FILE = WORKSPACE / "_agent_memory" / "respiration_log.jsonl"

# =============================================
# 节律四拍状态机
# =============================================

RESPIRATION_STAGES = ["idle", "activation", "suspension", "evolution", "reset"]
STAGE_LABELS = {
    "idle": "空闲",
    "activation": "张力激活",
    "suspension": "梦境悬挂",
    "evolution": "通路演化",
    "reset": "归位复位",
}

# 用户节律阀门阈值
VALVE_THRESHOLDS = {
    "critical": {"allow_suspension": False, "allow_evolution": False, "max_stage": "idle"},
    "red": {"allow_suspension": False, "allow_evolution": False, "max_stage": "idle"},
    "warning": {"allow_suspension": True, "allow_evolution": False, "max_stage": "suspension"},
    "orange": {"allow_suspension": True, "allow_evolution": False, "max_stage": "suspension"},
    "green": {"allow_suspension": True, "allow_evolution": True, "max_stage": "evolution"},
}


class TensionRespirationCycle:
    """
    单个张力节点的呼吸周期。
    记录节点从检测到解决的完整生命周期。
    """

    def __init__(
        self,
        cycle_id: str,
        anchor_a: str,
        anchor_b: str,
        tension: float,
        hang_id: str | None = None,
    ):
        self.cycle_id = cycle_id
        self.anchor_a = anchor_a
        self.anchor_b = anchor_b
        self.tension = tension
        self.hang_id = hang_id
        self.stage = "activation"
        self.stage_history = [{"stage": "activation", "ts": time.time()}]
        self.evolution_cycles = 0
        self.created_at = time.time()
        self.last_updated = time.time()
        self.completed_at: float | None = None

    def advance(self, new_stage: str) -> bool:
        """推进到下一阶段（禁止跳跃和回退超过1步）"""
        current_idx = RESPIRATION_STAGES.index(self.stage)
        target_idx = RESPIRATION_STAGES.index(new_stage)

        # 允许：前进1步 or 回到idle（重置）or 同阶段（更新）
        if new_stage == self.stage:
            return True  # 同阶段，无变化
        if new_stage == "idle" and self.stage != "idle":
            # 重置：允许从任何非idle阶段回到idle
            self.stage = "idle"
            self.stage_history.append({"stage": "idle", "ts": time.time()})
            self.last_updated = time.time()
            return True
        if target_idx <= current_idx:
            # 不允许向后回退（除了idle）
            return False

        self.stage = new_stage
        self.stage_history.append({"stage": new_stage, "ts": time.time()})
        self.last_updated = time.time()
        return True

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "anchor_a": self.anchor_a,
            "anchor_b": self.anchor_b,
            "tension": self.tension,
            "hang_id": self.hang_id,
            "stage": self.stage,
            "stage_label": STAGE_LABELS.get(self.stage, self.stage),
            "evolution_cycles": self.evolution_cycles,
            "stage_history": self.stage_history,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "completed_at": self.completed_at,
            "age_seconds": time.time() - self.created_at,
        }


class TensionRespirator:
    """
    张力呼吸器主控。

    职责：
      1. 管理多个并行的呼吸周期（T0/T1/T2 共享）
      2. 读取用户节律阀门（body_regulation.json）
      3. 在各阶段调用对应子模块（T0/T1/T2）
      4. 提供节律状态报告
    """

    def __init__(self):
        self._cycles: dict[str, TensionRespirationCycle] = {}
        self._counter = 0
        self._valve_state = "green"  # 默认全速
        self._load()

    def _load(self):
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                for cdict in data.get("cycles", []):
                    c = TensionRespirationCycle(
                        cycle_id=cdict["cycle_id"],
                        anchor_a=cdict["anchor_a"],
                        anchor_b=cdict["anchor_b"],
                        tension=cdict["tension"],
                        hang_id=cdict.get("hang_id"),
                    )
                    c.stage = cdict.get("stage", "activation")
                    c.stage_history = cdict.get("stage_history", c.stage_history)
                    c.evolution_cycles = cdict.get("evolution_cycles", 0)
                    if cdict.get("completed_at"):
                        c.completed_at = cdict["completed_at"]
                    self._cycles[c.cycle_id] = c
                self._counter = data.get("_counter", 0)
                self._valve_state = data.get("valve_state", "green")
            except Exception:
                self._counter = 0

    def _save(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "cycles": [c.to_dict() for c in self._cycles.values()],
            "_counter": self._counter,
            "valve_state": self._valve_state,
            "updated_at": time.time(),
        }
        STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _next_id(self) -> str:
        self._counter += 1
        return f"RESP-{self._counter:04d}"

    def _read_valve(self) -> str:
        """读取用户节律阀门状态"""
        reg_file = WORKSPACE / "_agent_memory" / "body_regulation.json"
        if reg_file.exists():
            try:
                data = json.loads(reg_file.read_text(encoding="utf-8"))
                zone = data.get("posture_zone", "green")
                if zone in VALVE_THRESHOLDS:
                    self._valve_state = zone
                    return zone
            except Exception:
                pass
        return self._valve_state

    def _valve_allows(self, stage: str) -> bool:
        """检查阀门是否允许进入指定阶段"""
        valve = self._read_valve()
        config = VALVE_THRESHOLDS.get(valve, VALVE_THRESHOLDS["green"])
        stage_order = ["idle", "activation", "suspension", "evolution", "reset"]
        max_idx = stage_order.index(config["max_stage"])

        if stage == "idle":
            return True
        if stage not in stage_order:
            return False
        return stage_order.index(stage) <= max_idx

    def register_tension(
        self,
        anchor_a: str,
        anchor_b: str,
        tension: float,
        hang_id: str | None = None,
    ) -> TensionRespirationCycle:
        """
        注册一个新的张力呼吸周期（从 T0 矛盾蒸馏器调用）。

        立即进入 activation 阶段。
        阀门关闭（critical/red）→ 停在 activation，不推进。
        """
        # 检查是否有相同锚点对的活跃周期
        for c in self._cycles.values():
            if c.completed_at is None:
                if {c.anchor_a, c.anchor_b} == {anchor_a, anchor_b}:
                    return c  # 已存在，返回现存的

        cycle_id = self._next_id()
        cycle = TensionRespirationCycle(
            cycle_id=cycle_id,
            anchor_a=anchor_a,
            anchor_b=anchor_b,
            tension=tension,
            hang_id=hang_id,
        )
        self._cycles[cycle_id] = cycle

        # 阀门检查
        valve = self._read_valve()
        if not self._valve_allows("suspension"):
            # 阀门关闭：停在activation，等待阀门打开
            self._log({
                "event": "registered_blocked_by_valve",
                "cycle_id": cycle_id,
                "valve": valve,
                "anchor_a": anchor_a,
                "anchor_b": anchor_b,
            })

        self._save()
        return cycle

    def advance_cycle(self, cycle_id: str, new_stage: str) -> bool:
        """
        推进一个呼吸周期到新阶段。

        由 T2 失谐放大器（T2→suspension）、T0 矛盾蒸馏器（T0→activation）等调用。
        """
        if cycle_id not in self._cycles:
            return False
        cycle = self._cycles[cycle_id]

        # 阀门检查
        if not self._valve_allows(new_stage):
            return False  # 阀门阻止

        ok = cycle.advance(new_stage)
        if ok:
            self._save()
            self._log({
                "event": "stage_advanced",
                "cycle_id": cycle_id,
                "from": cycle.stage_history[-2]["stage"] if len(cycle.stage_history) >= 2 else "init",
                "to": new_stage,
                "valve": self._valve_state,
            })
        return ok

    def complete_cycle(self, cycle_id: str, resolution: str):
        """完成一个呼吸周期（由 T3 或外部调用）"""
        if cycle_id not in self._cycles:
            return
        cycle = self._cycles[cycle_id]
        cycle.stage = "reset"
        cycle.completed_at = time.time()
        cycle.stage_history.append({"stage": "reset", "ts": time.time(), "resolution": resolution})
        self._save()
        self._log({
            "event": "cycle_completed",
            "cycle_id": cycle_id,
            "resolution": resolution,
        })

    def tick_evolution(self, cycle_id: str) -> bool:
        """
        演化节拍：周期 +1。
        仅在 evolution 阶段有效。
        """
        if cycle_id not in self._cycles:
            return False
        cycle = self._cycles[cycle_id]
        if cycle.stage != "evolution":
            return False
        cycle.evolution_cycles += 1
        cycle.last_updated = time.time()
        self._save()
        return True

    def get_active_cycles(self, stage: str | None = None) -> list[dict]:
        result = []
        for c in self._cycles.values():
            if c.completed_at is not None:
                continue
            if stage is not None and c.stage != stage:
                continue
            result.append(c.to_dict())
        return sorted(result, key=lambda x: x["tension"], reverse=True)

    def get_summary(self) -> dict:
        all_c = list(self._cycles.values())
        active = [c for c in all_c if c.completed_at is None]
        by_stage = {}
        for c in active:
            by_stage.setdefault(c.stage, 0)
            by_stage[c.stage] += 1
        return {
            "total_cycles": len(all_c),
            "active": len(active),
            "completed": len(all_c) - len(active),
            "by_stage": {STAGE_LABELS.get(k, k): v for k, v in by_stage.items()},
            "valve_state": self._valve_state,
            "highest_tension_active": max((c.tension for c in active), default=0),
        }

    def _log(self, entry: dict):
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({**entry, "ts": time.time()}, ensure_ascii=False) + "\n")


# =============================================
# 全局实例
# =============================================

_respirator: TensionRespirator | None = None


def get_respirator() -> TensionRespirator:
    global _respirator
    if _respirator is None:
        _respirator = TensionRespirator()
    return _respirator


def register_tension_cycle(
    anchor_a: str,
    anchor_b: str,
    tension: float,
    hang_id: str | None = None,
) -> str:
    """便捷入口：注册张力周期"""
    cycle = get_respirator().register_tension(anchor_a, anchor_b, tension, hang_id)
    return cycle.cycle_id


def advance_stage(cycle_id: str, new_stage: str) -> bool:
    return get_respirator().advance_cycle(cycle_id, new_stage)


def tick_evolution(cycle_id: str) -> bool:
    return get_respirator().tick_evolution(cycle_id)


def complete_cycle(cycle_id: str, resolution: str = ""):
    get_respirator().complete_cycle(cycle_id, resolution)


def get_active_report() -> dict:
    return get_respirator().get_summary()


# =============================================
# CLI
# =============================================

if __name__ == "__main__":
    resp = get_respirator()

    print("=== 张力呼吸器演示 ===\n")

    # 阀门状态
    valve = resp._read_valve()
    print(f"当前阀门状态: {valve}\n")

    # 注册三个张力周期
    cycles = [
        resp.register_tension("anchor_cortex", "anchor_time", 0.81),
        resp.register_tension("anchor_learning", "anchor_heritage", 0.72),
        resp.register_tension("anchor_body", "anchor_dream", 0.45),
    ]
    for c in cycles:
        print(f"注册: {c.cycle_id} [{STAGE_LABELS[c.stage]}] {c.anchor_a}↔{c.anchor_b} (t={c.tension:.2f})")

    print()

    # 推进到 suspension（T2 失谐放大）
    print("=== 推进到 suspension ===")
    for c in cycles:
        if resp.advance_cycle(c.cycle_id, "suspension"):
            print(f"  {c.cycle_id}: activation → suspension ✓")
        else:
            print(f"  {c.cycle_id}: 阀门阻止（当前阀门={valve}）")

    print()

    # 演化节拍
    print("=== 演化节拍（3次）===")
    for _ in range(3):
        for c in cycles:
            if resp.tick_evolution(c.cycle_id):
                pass  # 暂时不打印
    print(f"  cycles={cycles[0].cycle_id} 的演化节拍: {cycles[0].evolution_cycles}")

    print()
    print("=== 呼吸摘要 ===")
    summary = resp.get_summary()
    print(f"总周期: {summary['total_cycles']}")
    print(f"活跃: {summary['active']}")
    print(f"按阶段: {summary['by_stage']}")
    print(f"阀门: {summary['valve_state']}")
    print()
    print("=== 活跃周期详情 ===")
    for ac in resp.get_active_cycles():
        print(f"  {ac['cycle_id']} [{STAGE_LABELS[ac['stage']]}] t={ac['tension']:.2f} age={ac['age_seconds']:.0f}s")
