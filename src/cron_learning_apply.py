"""
cron_learning_apply.py — [P3/Qwen] 递归学习环消费端（闭环触发器）

目的：把"张力→认知差→学习→行为改变→新张力"这条递归环真正接上 cron。
此前生产端(dream_consolidation T0→tension_distiller)能产出 WreckageNode，
但消费端(learning_apply)不在 cron，矛盾蒸馏出来后无人消费 → 环从未转过一圈。

本任务每 30 分钟：
  1. 生产（兜底）：若 tension_queue.json 缺失/过旧，先跑 tension_distiller 蒸馏
  2. 消费：统计 contradiction_type + behavior_state.conflict_log 的 conflict_type
  3. 应用：同类 ≥3 次 → 经 LearningApplicator 写一条学习行为变更（告警队列）
  4. 记账：写 learning_action_log.json 记录本轮环是否转了一圈

设计意图：情感/张力是梯度（损失函数），本任务是梯度下降的执行器——
让"不舒服"真的改变行为，而非只被感知。
"""

import json
import sys
import time
import os
from pathlib import Path
from datetime import datetime, timezone

WS = Path(r"C:\Users\qq366410837\.qclaw\workspace")
SRC = WS / "src"
AGENT = WS / "_agent_memory"
MEMORY = WS / "memory"
sys.path.insert(0, str(SRC))

TENSION_QUEUE = AGENT / "tension_queue.json"
BEHAVIOR_STATE = AGENT / "behavior_state.json"
LEARNING_LOG = AGENT / "learning_action_log.json"
LEARNING_ALERTS = MEMORY / "_learning_alerts.jsonl"
CURIOSITY_EVENTS = MEMORY / "curiosity_events.jsonl"

THRESHOLD = 3          # 同类出现 ≥3 次才应用（防噪声）
STALE_SECONDS = 1800   # 队列超过 30 分钟视为过旧，重蒸馏

# 好奇事件阈值
ERROR_THRESHOLD = 0.4   # error_score ≥ 此值视为"结构性盲区"
OVERCONFIDENCE = 0.15   # conf_delta ≥ 此值视为"持续自我低估"


def _load_json(path: Path, fallback=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _produce_if_needed() -> dict:
    """生产兜底：队列缺失或过旧则蒸馏。返回 {produced, nodes}。"""
    need = True
    if TENSION_QUEUE.exists():
        age = time.time() - TENSION_QUEUE.stat().st_mtime
        if age < STALE_SECONDS:
            need = False
    if not need:
        return {"produced": False, "reason": "fresh"}
    try:
        import tension_distiller as td
        d = td.TensionDistiller()
        rep = d.distill(days=7, top_n=50)
        nodes = getattr(rep, "nodes", []) or []
        return {"produced": True, "nodes": len(nodes)}
    except Exception as e:
        return {"produced": False, "reason": f"distill_err:{e}"}


def _count_types() -> dict:
    """合并 tension_queue + behavior_state.conflict_log 的类型计数。"""
    counts = {}
    q = _load_json(TENSION_QUEUE, {})
    for n in q.get("nodes", []):
        t = n.get("contradiction_type") or n.get("type")
        if t:
            counts[t] = counts.get(t, 0) + 1
    bs = _load_json(BEHAVIOR_STATE, {})
    for c in bs.get("conflict_log", []):
        t = c.get("conflict_type")
        if t:
            counts[t] = counts.get(t, 0) + 1
    return counts


def _count_curiosity() -> dict:
    """
    读取 curiosity_events.jsonl，提取两类信号：
    - structural_blind: error_score ≥ ERROR_THRESHOLD（"我为什么会漏掉这个"）
    - self_underestimated: conf_delta ≥ OVERCONFIDENCE（"我低估了自己"）
    返回 {blind_count, underest_count, events_read}
    """
    blind_count = 0
    underest_count = 0
    total = 0
    if not CURIOSITY_EVENTS.exists():
        return {"blind_count": 0, "underest_count": 0, "events_read": 0}
    try:
        lines = CURIOSITY_EVENTS.read_text(encoding="utf-8").strip().splitlines()
        total = len(lines)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            es = ev.get("error_score", 0.0)
            cd = ev.get("confidence_delta", 0.0)
            if es >= ERROR_THRESHOLD:
                blind_count += 1
            if cd >= OVERCONFIDENCE:
                underest_count += 1
    except Exception:
        pass
    return {"blind_count": blind_count, "underest_count": underest_count, "events_read": total}


def _apply(type_name: str, count: int) -> dict:
    """消费：经 LearningApplicator 写一条学习行为变更。"""
    return _apply_common(type_name, count, "recursive_loop")


def _apply_curiosity(signal_type: str, count: int) -> dict:
    """
    消费好奇事件：
    - structural_blind: error_score 持续偏高 → "我的拓扑感知有系统性盲区"
    - self_underestimated: conf_delta 持续偏高 → "我低估了自己"
    """
    label = {
        "structural_blind": ("结构性盲区", "alert+memo"),
        "self_underestimated": ("持续自我低估", "alert+memo"),
    }.get(signal_type, (signal_type, "alert"))

    content = {
        "structural_blind": f"好奇事件检测到结构性盲区信号（[{signal_type}] 共 {count} 次），"
                            f"预测误差持续偏高，建议审视锚点选择策略是否存在系统性偏向",
        "self_underestimated": f"好奇事件检测到持续自我低估（[{signal_type}] 共 {count} 次），"
                               f"锚点置信度持续超预期上升，建议修正自我评估基线",
    }.get(signal_type, f"好奇事件 [{signal_type}] 共 {count} 次")

    return _apply_common(signal_type, count, f"curiosity:{signal_type}", content=content)


def _apply_common(type_name: str, count: int, source: str, content: str = None) -> dict:
    """通用应用封装。"""
    if content is None:
        content = (f"递归学习环检测到重复矛盾类型 [{type_name}] 共 {count} 次，"
                  f"建议收紧对应认知刹车/调整行为策略（自动生成，待造物主确认）")
    try:
        from learning_apply import LearningApplicator
        product = {
            "id": f"lp_auto_{int(time.time())}",
            "content": content,
            "confidence": min(0.5 + count * 0.1, 0.95),
            "support": count,
            "track": "library",
            "action": "notify_creator",
            "source_pattern": f"{source}:{type_name}",
        }
        app = LearningApplicator()
        res = app.apply([{"decision": "accept", "product": product}])
        return {"applied": res.get("applied", 0), "errors": res.get("errors", 0)}
    except Exception as e:
        return {"applied": 0, "errors": 1, "err": str(e)}


def run() -> dict:
    prod = _produce_if_needed()
    counts = _count_types()
    triggered = {t: c for t, c in counts.items() if c >= THRESHOLD}

    applied = []
    for t, c in triggered.items():
        r = _apply(t, c)
        applied.append({"type": t, "count": c, **r})

    # ── 好奇事件消费（新增）────────────────────────────
    cq = _count_curiosity()
    curiosity_applied = []
    if cq["blind_count"] >= THRESHOLD:
        r = _apply_curiosity("structural_blind", cq["blind_count"])
        curiosity_applied.append({"signal": "structural_blind", "count": cq["blind_count"], **r})
    if cq["underest_count"] >= THRESHOLD:
        r = _apply_curiosity("self_underestimated", cq["underest_count"])
        curiosity_applied.append({"signal": "self_underestimated", "count": cq["underest_count"], **r})

    # 记账
    log = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "produce": prod,
        "type_counts": counts,
        "triggered": triggered,
        "applied": applied,
        "curiosity": cq,
        "curiosity_applied": curiosity_applied,
        "loop_turned": len(applied) > 0 or len(curiosity_applied) > 0,
    }
    try:
        history = _load_json(LEARNING_LOG, [])
        if not isinstance(history, list):
            history = []
        history.append(log)
        LEARNING_LOG.write_text(
            json.dumps(history[-50:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    return log


def main():
    log = run()
    print(f"[learning_apply] produce={log['produce']}")
    print(f"[learning_apply] type_counts={log['type_counts']}")
    print(f"[learning_apply] triggered={log['triggered']}")
    cq = log.get("curiosity", {})
    print(f"[learning_apply] curiosity_events={cq.get('events_read',0)} "
          f"blind={cq.get('blind_count',0)} underest={cq.get('underest_count',0)}")
    print(f"[learning_apply] curiosity_applied={log['curiosity_applied']}")
    print(f"[learning_apply] loop_turned={log['loop_turned']}")
    for a in log["applied"]:
        print(f"[learning_apply] applied {a['type']} x{a['count']}: {a}")


if __name__ == "__main__":
    main()
