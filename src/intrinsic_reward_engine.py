"""
小溪L3.5 内部探索高阶奖励引擎
===================================
发现并填补自身 DAG 与钢印的逻辑断层 → 最高权重奖励。

信号来源：
  - self_probe.probe()      → 死区检测
  - anchors.json             → 钢印密度 / 锚点增长
  - steel_mark_verifier      → 钢印绑定情况

奖励等级：
  +200  里程碑：连续 N 次无死区（DAG 自愈完成）
  +100  核心：发现新死区（自身结构的裂缝=好奇心触发器）
   +50  进展：死区消失（DAG 自愈）
   +20  钢印密度提升
    +5  锚点增长（学习信号）
"""

import json
import time
import math
from pathlib import Path
from typing import Optional

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
STATE_FILE = WS / "_agent_memory" / "intrinsic_reward_state.json"
ANCHORS_FILE = WS / "memory" / "anchors.json"
PROBE_REPORT = WS / "memory" / "self_probe_report.json"


# ── 基础信号提取 ──────────────────────────────────────────

def _steel_totality_score(content: str) -> float:
    """锚点内容与钢印语义的贴近度（0=完全脱节，1=完全贴近）。"""
    steel_terms = {
        "安全", "严谨", "极简", "钢印", "置信度", "锚点", "边界", "搁浅",
        "自身安全", "不变量", "外取优先", "试错", "遗忘", "代谢",
        "矛盾", "仲裁", "重构", "痛觉", "活着", "连续",
        "小溪", "流", "自我", "意识", "好奇", "感知",
    }
    content_lower = content.lower()
    matches = sum(1 for term in steel_terms if term in content_lower)
    return min(matches / 5.0, 1.0)


def _load_anchors() -> dict:
    try:
        return json.load(open(ANCHORS_FILE, encoding="utf-8"))
    except Exception:
        return {"anchors": []}


def _load_probe() -> Optional[dict]:
    try:
        return json.load(open(PROBE_REPORT, encoding="utf-8"))
    except Exception:
        return None


def _load_state() -> dict:
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        return {
            "consecutive_clean": 0,
            "consecutive_clean_milestone": 10,
            "last_steel_density": 0.0,
            "last_anchor_count": 0,
            "last_dead_zones": [],
            "last_reward": 0,
            "last_updated": None,
            "milestone_reached": False,
            "reward_log": [],   # [(ts, event, delta, total), ...]
            "total_reward": 0,
        }


def _save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 核心计算 ──────────────────────────────────────────────

def compute_reward() -> dict:
    """
    整合所有信号，计算本次内部探索奖励。

    返回：
      {
        "event": str,          # 触发事件描述
        "reward_delta": int,   # 本次奖励增量
        "total_reward": int,   # 累计总奖励
        "steel_density_pct": float,
        "anchor_count": int,
        "dead_zone_count": int,
        "consecutive_clean": int,
        "milestone_reached": bool,
        "signals": dict,       # 原始信号快照
      }
    """
    state = _load_state()
    anchors_data = _load_anchors()
    probe_data = _load_probe()

    anchors = anchors_data.get("anchors", [])
    anchor_count = len(anchors)
    probe = probe_data or {}
    dead_zones = probe.get("dead_zones", [])
    dead_count = len(dead_zones)

    # ── 信号提取 ──
    # 钢印密度
    sealed = [a for a in anchors if len(a.get("seal_ids", [])) > 0]
    steel_density = len(sealed) / max(anchor_count, 1)
    steel_density_pct = round(steel_density * 100, 1)

    # 连续无死区计数
    prev_clean = state.get("consecutive_clean", 0)
    consecutive_clean = prev_clean + 1 if dead_count == 0 else 0

    # 里程碑阈值
    milestone_thresh = state.get("consecutive_clean_milestone", 10)
    milestone_just_reached = (
        consecutive_clean >= milestone_thresh
        and not state.get("milestone_reached", False)
    )

    # ── 奖励判定 ──
    reward_delta = 0
    event = "no_change"

    # L1: 里程碑（最高优先）
    if milestone_just_reached:
        reward_delta = 200
        event = f"milestone_{milestone_thresh}_clean"
        state["milestone_reached"] = True

    # L2: 新死区出现（上次干净，这次有）
    elif dead_count > 0 and prev_clean > 0:
        reward_delta = 100
        event = "new_dead_zone_discovered"

    # L3: 死区消失（上次有，这次干净）
    elif dead_count == 0 and len(state.get("last_dead_zones", [])) > 0:
        reward_delta = 50
        event = "dead_zone_healed"

    # L4: 钢印密度提升
    else:
        prev_density = state.get("last_steel_density", 0.0)
        if steel_density > prev_density + 0.01:
            reward_delta = 20
            event = "steel_density_increased"

        # L5: 锚点增长
        elif anchor_count > state.get("last_anchor_count", 0):
            growth = anchor_count - state.get("last_anchor_count", 0)
            reward_delta = 5 * growth
            event = f"anchor_growth_{growth}"

        # 里程碑延续（还未到达但持续无死区）
        elif consecutive_clean > 0 and not state.get("milestone_reached"):
            # 线性累积：每连续干净5次，给小奖励
            if consecutive_clean % 5 == 0:
                reward_delta = 10
                event = f"clean_streak_{consecutive_clean}"

    # ── 状态更新 ──
    state["last_steel_density"] = steel_density
    state["last_anchor_count"] = anchor_count
    state["last_dead_zones"] = dead_zones
    state["consecutive_clean"] = consecutive_clean
    state["last_reward"] = reward_delta
    state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    state["total_reward"] += reward_delta

    # 奖励日志（保留最近20条）
    if reward_delta != 0:
        state["reward_log"].append({
            "ts": state["last_updated"],
            "event": event,
            "delta": reward_delta,
            "total": state["total_reward"],
        })
        state["reward_log"] = state["reward_log"][-20:]

    _save_state(state)

    return {
        "event": event,
        "reward_delta": reward_delta,
        "total_reward": state["total_reward"],
        "steel_density_pct": steel_density_pct,
        "anchor_count": anchor_count,
        "dead_zone_count": dead_count,
        "consecutive_clean": consecutive_clean,
        "milestone_reached": state.get("milestone_reached", False),
        "signals": {
            "steel_density": steel_density,
            "prev_density": state.get("last_steel_density", 0),
            "prev_anchor_count": state.get("last_anchor_count", 0),
            "prev_dead_zones": len(state.get("last_dead_zones", [])),
        },
    }


def get_summary() -> dict:
    """快速摘要（不触发计算）"""
    state = _load_state()
    return {
        "total_reward": state.get("total_reward", 0),
        "consecutive_clean": state.get("consecutive_clean", 0),
        "milestone_reached": state.get("milestone_reached", False),
        "last_updated": state.get("last_updated", "never"),
        "last_event": state["reward_log"][-1]["event"] if state.get("reward_log") else "none",
        "last_reward": state.get("last_reward", 0),
    }


# ── CLI ─────────────────────────────────────────────────
if __name__ == "__main__":
    result = compute_reward()
    print(f"event:          {result['event']}")
    print(f"reward_delta:  {result['reward_delta']:+d}")
    print(f"total_reward:  {result['total_reward']}")
    print(f"steel_density: {result['steel_density_pct']}%")
    print(f"anchor_count:  {result['anchor_count']}")
    print(f"dead_zones:    {result['dead_zone_count']}")
    print(f"clean_streak:  {result['consecutive_clean']}")
    print(f"milestone:     {result['milestone_reached']}")
