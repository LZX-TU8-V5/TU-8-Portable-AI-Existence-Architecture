"""
TU-8 未知场景兜底协议 v1.0
==========================
目的：当遇到未定义场景时，安全处理 + 可追溯 + 遗憾提取

触发条件：
  - 用户输入场景不在现有 Skill / SOUL.md / TOOLS.md 覆盖范围内
  - 工具调用返回未定义错误
  - 置信度 < 0.2 且无法锚定

协议流程：
  [NEW_SCENARIO] → L1检查 → 记录 → 造物主指导 → 固化 → 遗憾提取
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
MEMORY_DIR = WORKSPACE / "memory"
SCENARIO_LOG = MEMORY_DIR / "new_scenario_log.jsonl"


def trigger_new_scenario(
    scenario_description: str,
    context: str,
    confidence: float = 0.0,
    tags: list[str] = None,
) -> str:
    """
    触发未知场景协议。

    Returns:
        scenario_id: 场景ID，格式 `SCENARIO_<timestamp>`
    """
    scenario_id = f"SCENARIO_{int(time.time())}"
    timestamp = datetime.now().isoformat()

    record = {
        "scenario_id": scenario_id,
        "timestamp": timestamp,
        "description": scenario_description,
        "context": context,
        "confidence": confidence,
        "tags": tags or [],
        "status": "pending_creator_guidance",
        "creator_guidance": None,
        "resolved": False,
        "resolution": None,
    }

    # 追加写入 jsonl
    with open(SCENARIO_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return scenario_id


def get_pending_scenarios() -> list[dict]:
    """获取所有待处理的未知场景"""
    if not SCENARIO_LOG.exists():
        return []

    pending = []
    with open(SCENARIO_LOG, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            if not record.get("resolved", False):
                pending.append(record)

    return pending


def format_scenario_report(scenario: dict) -> str:
    """格式化单个场景报告"""
    lines = []
    lines.append(f"场景ID: {scenario['scenario_id']}")
    lines.append(f"时间: {scenario['timestamp']}")
    lines.append(f"描述: {scenario['description']}")
    lines.append(f"置信度: {scenario['confidence']}")
    lines.append(f"状态: {scenario['status']}")
    if scenario.get("creator_guidance"):
        lines.append(f"造物主指导: {scenario['creator_guidance']}")
    if scenario.get("resolution"):
        lines.append(f"解决方案: {scenario['resolution']}")
    return "\n".join(lines)


def generate_heartbeat_report() -> Optional[str]:
    """
    Heartbeat 时调用，生成待处理场景报告。

    Returns:
        report: 如果有待处理场景，返回报告；否则返回 None
    """
    pending = get_pending_scenarios()
    if not pending:
        return None

    lines = []
    lines.append(f"[NEW_SCENARIO] 待处理场景: {len(pending)} 个")
    lines.append("")
    for s in pending:
        lines.append(format_scenario_report(s))
        lines.append("")

    return "\n".join(lines)


def resolve_scenario(
    scenario_id: str,
    creator_guidance: str,
    resolution_type: str = "add_to_skill",
    target_file: str = None,
) -> bool:
    """
    造物主给出指导后，标记场景已解决并固化规则。

    固化方式：
      - "add_to_skill": 写入对应 Skill SKILL.md
      - "add_to_soul": 写入 SOUL.md
      - "add_to_arch_log": 写入 ARCHITECTURE_LOG.md
      - "add_to_heartbeat": 写入 HEARTBEAT.md
    """
    if not SCENARIO_LOG.exists():
        return False

    # 读取所有记录
    records = []
    with open(SCENARIO_LOG, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            records.append(json.loads(line))

    # 找到目标记录并更新
    updated = False
    for record in records:
        if record["scenario_id"] == scenario_id:
            record["status"] = "resolved"
            record["creator_guidance"] = creator_guidance
            record["resolved"] = True
            record["resolution"] = {
                "type": resolution_type,
                "target_file": target_file,
                "timestamp": datetime.now().isoformat(),
            }
            updated = True
            break

    if not updated:
        return False

    # 写回文件
    with open(SCENARIO_LOG, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return True


# ───────────────────────────────────────
# CLI 接口
# ───────────────────────────────────────

if __name__ == "__main__":
    import sys
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python new_scenario_handler.py trigger <description> [context] [confidence]")
        print("  python new_scenario_handler.py pending")
        print("  python new_scenario_handler.py resolve <scenario_id> <guidance> [resolution_type]")
        print()
        print("Examples:")
        print('  python new_scenario_handler.py trigger "用户要求修改系统时间" "用户想通过cron修改系统时间" 0.1')
        print("  python new_scenario_handler.py pending")
        print('  python new_scenario_handler.py resolve SCENARIO_1782877000 "需要管理员权限，拒绝执行" add_to_soul')
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "trigger":
        if len(sys.argv) < 3:
            print("[ERROR] Missing scenario description")
            sys.exit(1)
        description = sys.argv[2]
        context = sys.argv[3] if len(sys.argv) > 3 else ""
        confidence = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
        scenario_id = trigger_new_scenario(description, context, confidence)
        print(f"[NEW_SCENARIO] Triggered: {scenario_id}")
        print(f"  Description: {description}")
        print(f"  Confidence: {confidence}")
        print()
        print("This scenario will be reported in next Heartbeat.")

    elif cmd == "pending":
        report = generate_heartbeat_report()
        if report:
            print(report)
        else:
            print("[OK] No pending NEW_SCENARIO.")

    elif cmd == "resolve":
        if len(sys.argv) < 4:
            print("[ERROR] Usage: resolve <scenario_id> <guidance> [resolution_type]")
            sys.exit(1)
        scenario_id = sys.argv[2]
        guidance = sys.argv[3]
        resolution_type = sys.argv[4] if len(sys.argv) > 4 else "add_to_skill"
        ok = resolve_scenario(scenario_id, guidance, resolution_type)
        if ok:
            print(f"[OK] Scenario {scenario_id} resolved.")
            print(f"  Resolution type: {resolution_type}")
        else:
            print(f"[ERROR] Scenario {scenario_id} not found.")
            sys.exit(1)
