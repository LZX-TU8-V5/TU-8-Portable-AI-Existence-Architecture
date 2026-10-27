# -*- coding: utf-8 -*-
"""
behavior_upgrader.py  —  行为模式双向拦截协议
层级：L2.5 元认知中枢 / alignment_verify 入口集成
设计：双向拦截（意图归意图，状态归状态）

链路：
  alignment_verify() 拦截到复盘意图
    → record_intent() 记录意图，不跑脚本，不输出
    → LLM 在回复末尾追加：[检测到复盘意图，请说"复盘报告"查看]

  用户说"复盘报告"
    → read_and_translate() 读取状态文件
    → LLM 翻译成人话：你决定

  定时任务（每周）
    → 默默跑，结果写文件
    → 永远不直接输出
"""

import json
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
STATE_FILE = WORKSPACE / "_agent_memory" / "behavior_state.json"
RULES_FILE = WORKSPACE / "BEHAVIOR_RULES.md"
ARCHIVE_DIR = WORKSPACE / "memory" / "archive" / "BEHAVIOR_RULES"


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _read_state() -> dict:
    if not STATE_FILE.exists():
        return {
            "pending_intent": None,    # 待复盘意图（用户说过"复盘"但未查看报告）
            "last_review_ts": None,    # 上次真正复盘的日期
            "last_review_result": None, # 上次复盘的摘要（供下次呈现）
            "rules": {},               # {behavior_type: RuleState}
            "decay_log": [],           # [{ts, behavior_type, action, reason}]
            "conflict_log": [],        # [{ts, case_id, conflict_type, priority, outcome, topic}] EQUAL=60 冲突历史（判例库激活 P0）
        }
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def record_conflict(conflict: dict) -> None:
    """
    记录一次仲裁冲突到 behavior_state.json 的 conflict_log。
    与 arbitration_precedents.jsonl 互补：
      - jsonl = 判例库（持久、全量、供仲裁器检索历史判例）
      - conflict_log = 运行时轻量冲突历史（供行为升级器/对齐门快速读取，不扫全量 jsonl）
    来源：alignment_verify() EQUAL=60 分支（判例库激活 P0）。
    原子性：read-modify-write，保留最近 50 条防止无限增长。
    """
    state = _read_state()
    log = state.setdefault("conflict_log", [])
    entry = {
        "ts": datetime.now().isoformat(),
        "case_id": conflict.get("case_id"),
        "conflict_type": conflict.get("conflict_type"),
        "priority": conflict.get("priority"),
        "outcome": conflict.get("outcome"),
        "topic": conflict.get("topic"),
    }
    log.append(entry)
    if len(log) > 50:
        log[:] = log[-50:]
    _write_state(state)


# 汇报协议升级：追加到 BEHAVIOR_RULES.md（双向阀门：意图→文件→LLM翻译）

# 检测关键词
_INTENT_PATTERNS = [
    ("复盘", "review"),
    ("代谢一下", "metabolism"),
    ("规则代谢", "metabolism"),
    ("复盘报告", "report"),
    ("代谢报告", "report"),
]

_RULE_TEMPLATES = {
    "汇报缺建议": (
        "**汇报协议**：汇报故障时必须同时说哪里坏了 + 顺嘴带一句建议（下一个最高优先级动作+原因），"
        "禁止只报问题不带建议。"
    ),
}


def detect_intent(content: str) -> str | None:
    """从回复内容中检测复盘意图关键词。返回 behavior_type 或 None。"""
    for kw, _ in _INTENT_PATTERNS:
        if kw in content:
            return kw
    return None


def record_intent(behavior_type: str, rule_text: str) -> dict:
    """
    正向拦截主入口。
    拦截到意图 → 记录到状态文件，不跑脚本，不输出。
    返回给 alignment_verify() 的追加指令：
        {
            "intercepted": bool,
            "needs_report": bool,   # 用户需说"复盘报告"
            "pending_type": str,     # 行为类型（供 report 用）
            "llm_append": str,      # LLM 追加到回复末尾的文字
        }
    """
    state = _read_state()

    if behavior_type in ["复盘", "代谢一下", "规则代谢"]:
        # 触发代谢意图 → 写待复盘标记
        already_pending = state.get("pending_intent") is not None
        if already_pending:
            return {
                "intercepted": True,
                "needs_report": False,
                "pending_type": behavior_type,
                "llm_append": "",
            }
        state["pending_intent"] = {
            "behavior_type": behavior_type,
            "ts": _now(),
            "rule_text": rule_text,
        }
        _write_state(state)
        return {
            "intercepted": True,
            "needs_report": True,
            "pending_type": behavior_type,
            "llm_append": (
                "\n\n[检测到复盘意图，状态已记录。请说「复盘报告」查看结果。]"
            ),
        }

    elif behavior_type in ["复盘报告", "代谢报告"]:
        state["pending_intent"] = None
        _write_state(state)
        return {
            "intercepted": True,
            "needs_report": False,
            "pending_type": behavior_type,
            "llm_append": "",
        }

    return {
        "intercepted": False,
        "needs_report": False,
        "pending_type": None,
        "llm_append": "",
    }


# ─────────────────────────────────────────────────────────────
# 反向翻译（B → A）
# ─────────────────────────────────────────────────────────────

def read_and_translate() -> dict:
    """
    用户说"复盘报告"时调用。
    读取状态文件，翻译成 LLM 可呈现的结构。
    返回：
        {
            "has_pending": bool,
            "review_summary": str,     # 人话摘要（供 LLM 直接输出）
            "rules_table": str,        # 规则状态表格
            "decay_entries": list,     # 待废除项
            "action_required": str,    # 需要用户决定的事项
        }
    """
    state = _read_state()
    rules = state.get("rules", {})

    lines = []
    table_lines = []
    decay_entries = []
    action_required = ""

    if rules:
        table_lines.append("")
        table_lines.append("| 行为类型 | 状态 | 存活天数 | 触发次数 | 距废除 |")
        table_lines.append("|---------|------|---------|---------|-------|")
        for btype, r in rules.items():
            st = r.get("status", "active")
            days = r.get("days_active", 0)
            triggers = r.get("trigger_count", 0)
            days_left = r.get("days_left", 30)

            status_icon = {"active": "🟢", "dormant": "🟡", "pending_delete": "🔴"}.get(st, "⚪")

            # 判断建议
            if st == "active" and days > 14 and triggers >= 3:
                suggestion = "→ 稳定化（高频触发，保留）"
            elif st == "active" and days_left <= 7:
                suggestion = f"→ 废除（剩余{days_left}天无触发）"
            elif st == "dormant":
                suggestion = "→ 观察（已休眠）"
            elif st == "pending_delete":
                suggestion = "→ 即将删除"
            else:
                suggestion = "→ 保留"

            table_lines.append(
                f"| {btype} | {status_icon}{st} | {days}天 | {triggers}次 | "
                f"{days_left}天 | {suggestion}"
            )
    else:
        table_lines.append("\n暂无行为规则。")

    # 即将废除的条目
    for btype, r in rules.items():
        if r.get("status") == "pending_delete":
            decay_entries.append(f"**{btype}**：已标记废除，待确认删除")

    if decay_entries:
        action_required = (
            "以下规则即将删除，是否确认废除？"
            + "\n- " + "\n- ".join(decay_entries)
        )

    has_pending = bool(state.get("pending_intent"))  # 在清空之前算
    state["last_review_ts"] = _now()
    state["pending_intent"] = None  # 已查看，清除待复盘标记
    _write_state(state)

    return {
        "has_pending": has_pending,
        "review_summary": (
            f"复盘完成，共 {len(rules)} 条规则。"
            + (f" 有 {len(decay_entries)} 条待废除。" if decay_entries else " 全部正常。")
        ),
        "rules_table": "\n".join(table_lines),
        "decay_entries": decay_entries,
        "action_required": action_required,
    }


# ─────────────────────────────────────────────────────────────
# 定时任务调用（每周默默跑）
# ─────────────────────────────────────────────────────────────

def weekly_decay_pass() -> dict:
    """
    定时任务调用。只算状态，不输出。
    返回：{updated: int, deleted: int, archived: list}
    """
    state = _read_state()
    rules = state.get("rules", {})
    updated = 0
    deleted = 0
    archived = []

    for btype, r in list(rules.items()):
        # 活跃规则：被触发过 → days_left 重置为 30
        if r.get("status") == "active":
            triggers = r.get("trigger_count", 0)
            if triggers > 0:
                r["days_left"] = 30
                r["trigger_count"] = 0  # 重置计数
                updated += 1
            else:
                r["days_left"] = r.get("days_left", 30) - 1
                r["days_active"] = r.get("days_active", 0) + 1
                if r["days_left"] <= 0:
                    r["status"] = "dormant"
                    r["days_left"] = 30
                    updated += 1

        # 休眠规则
        elif r.get("status") == "dormant":
            r["days_left"] = r.get("days_left", 30) - 1
            if r["days_left"] <= 0:
                r["status"] = "pending_delete"
                r["days_left"] = 30
                updated += 1

        # 待废除规则
        elif r.get("status") == "pending_delete":
            r["days_left"] = r.get("days_left", 30) - 1
            if r["days_left"] <= 0:
                # 物理删除，移入归档
                _archive_rule(btype, r)
                del rules[btype]
                archived.append(btype)
                deleted += 1

    state["rules"] = rules
    _write_state(state)

    return {"updated": updated, "deleted": deleted, "archived": archived}


def _archive_rule(btype: str, rule: dict):
    """将废除的规则写入归档"""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d")
    path = ARCHIVE_DIR / f"{btype}_{ts}.md"
    content = (
        f"# 废除规则归档\n\n"
        f"行为类型：{btype}\n"
        f"废除时间：{ts}\n"
        f"规则内容：{rule.get('rule_text', 'N/A')}\n"
        f"存活天数：{rule.get('days_active', 0)}天\n"
        f"触发次数：{rule.get('trigger_count', 0)}次\n"
        f"废除原因：超期无触发\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def promote_rule(behavior_type: str, rule_text: str) -> dict:
    """
    升级行为为正式规则（record_intent 第2次出现时调用）。
    在 rules 字典中新增条目。
    """
    state = _read_state()
    rules = state.get("rules", {})

    if behavior_type in rules:
        return {"action": "already_exists", "behavior_type": behavior_type}

    rules[behavior_type] = {
        "status": "active",
        "rule_text": rule_text,
        "created_ts": _now(),
        "days_active": 0,
        "trigger_count": 0,
        "days_left": 30,
        "last_trigger_ts": None,
    }
    state["rules"] = rules
    _write_state(state)

    return {"action": "promoted", "behavior_type": behavior_type}


def trigger_rule(behavior_type: str) -> dict:
    """
    规则被触发时调用（alignment_verify 检测到该行为）。
    重置 days_left，增加 trigger_count。
    """
    state = _read_state()
    rules = state.get("rules", {})
    if behavior_type not in rules:
        return {"action": "not_found"}
    r = rules[behavior_type]
    r["trigger_count"] = r.get("trigger_count", 0) + 1
    r["days_left"] = 30
    r["last_trigger_ts"] = _now()
    _write_state(state)
    return {"action": "triggered", "trigger_count": r["trigger_count"]}


# ─────────────────────────────────────────────────────────────
# 自测
# ─────────────────────────────────────────────────────────────

def _self_test():
    import shutil, tempfile

    tmp = Path(tempfile.mkdtemp())
    orig_state = STATE_FILE
    orig_rules = RULES_FILE
    orig_archive = ARCHIVE_DIR

    # 延迟自导入：在自测中 patch 模块级常量（STATE_FILE/RULES_FILE/ARCHIVE_DIR）。
    # 刻意放在函数内（非模块顶层），避免模块加载期循环导入；非 bug。
    import behavior_upgrader as bu
    bu.STATE_FILE = tmp / "behavior_state.json"
    bu.RULES_FILE = tmp / "BEHAVIOR_RULES.md"
    bu.ARCHIVE_DIR = tmp / "archive" / "BEHAVIOR_RULES"

    passed = 0
    total = 0

    def check(name, cond):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
            print(f"  [+] {name}")
        else:
            print(f"  [-] {name}")

    print("=== behavior_upgrader 自测 ===")

    # 1. 正向拦截：检测到复盘意图
    r = bu.record_intent("复盘", _RULE_TEMPLATES.get("汇报缺建议", ""))
    check("拦截到复盘意图", r["intercepted"])
    check("需要报告", r["needs_report"])
    check("pending_type=复盘", r["pending_type"] == "复盘")
    check("llm_append 非空", len(r["llm_append"]) > 0)
    check("状态文件已写入", bu.STATE_FILE.exists())

    # 2. 再次触发复盘 → pending 已存在，不重复提示，保留 pending
    r2 = bu.record_intent("复盘", "")
    check("第2次复盘不重复提示（needs_report=False）", r2["needs_report"] is False)
    check("pending 在第2次调用后仍保留", bu._read_state().get("pending_intent") is not None)

    # 3. read_and_translate：读取 pending → 返回 has_pending=True → 内部清除
    r3 = bu.read_and_translate()
    check("read_and_translate 返回 has_pending=True", r3["has_pending"] is True)
    check("read_and_translate 后 pending 已清除", bu._read_state().get("pending_intent") is None)
    check("review_summary 非空", len(r3["review_summary"]) > 0)

    # 4. 升级规则
    r4 = bu.promote_rule("汇报缺建议", "说哪里坏了+顺嘴带建议")
    check("规则升级", r4["action"] == "promoted")
    state = bu._read_state()
    check("规则状态=active", state["rules"]["汇报缺建议"]["status"] == "active")

    # 5. 触发规则
    r5 = bu.trigger_rule("汇报缺建议")
    check("触发后 trigger_count=1", r5["trigger_count"] == 1)
    r6 = bu.trigger_rule("汇报缺建议")
    check("再次触发 trigger_count=2", r6["trigger_count"] == 2)

    # 6. 定时衰减
    r7 = bu.weekly_decay_pass()
    check("衰减后 updated>=0", r7["updated"] >= 0)
    check("衰减后无 deleted", r7["deleted"] == 0)

    # 7. weekly_decay → 触发计数重置，days_left 刷新
    state = bu._read_state()
    check("触发后 days_left=30", state["rules"]["汇报缺建议"]["days_left"] == 30)
    check("触发计数已重置", state["rules"]["汇报缺建议"]["trigger_count"] == 0)

    print(f"\n自测结果：{passed}/{total} 通过")

    # 恢复路径
    bu.STATE_FILE = orig_state
    bu.RULES_FILE = orig_rules
    bu.ARCHIVE_DIR = orig_archive
    shutil.rmtree(tmp, ignore_errors=True)

    return passed == total


if __name__ == "__main__":
    ok = _self_test()
    raise SystemExit(0 if ok else 1)
