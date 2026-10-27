"""
shadow_protocol.py - 遗憾记录协议

功能：记录执行结果与预期不符的情况，提炼教训
触发：造物主不满意时手动调用

HP2 钩子：
  BEFORE — 可短路（跳过记录）
  AFTER  — 可修改/增强记录
  ON_TENSION — 遗憾强度异常时触发

使用方法：
    from shadow_protocol import log_regret
    log_regret(trigger, context, expected, actual, gap, lesson, action)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

WS = Path("~/.qclaw/workspace").expanduser()

# ── HP2 钩子运行器 ─────────────────────────────────

def _get_hp2_runner():
    try:
        sys.path.insert(0, str(WS / "src"))
        import importlib
        import hook_injector
        importlib.reload(hook_injector)
        return hook_injector.run_hooks, hook_injector.HookType
    except Exception:
        return None, None


def _run_hp2_before(ctx: dict) -> tuple:
    """HP2 BEFORE：可短路遗憾记录"""
    runner, HT = _get_hp2_runner()
    if not runner:
        return False, ctx
    try:
        result = runner("HP2", HT.BEFORE, ctx)
        short = result.get("short_circuited", False)
        for name, hctx in result.get("results", []):
            if isinstance(hctx, dict):
                ctx.update(hctx)
        return short, ctx
    except Exception:
        return False, ctx


def _run_hp2_after(ctx: dict, record: dict) -> dict:
    """HP2 AFTER：可修改/增强记录"""
    runner, HT = _get_hp2_runner()
    if not runner:
        return record
    try:
        result = runner("HP2", HT.AFTER, ctx, record)
        return result.get("final", record)
    except Exception:
        return record


# ── 工作目录 ─────────────────────────────────────────

def _workspace() -> str:
    return os.environ.get("QCLAW_WORKSPACE", os.path.expanduser("~/.qclaw/workspace"))


# ── 核心函数 ─────────────────────────────────────────

def log_regret(
    trigger: str,
    context: str,
    expected: str,
    actual: str,
    gap: str,
    lesson: str,
    action: str
) -> dict:
    """
    记录遗憾（执行结果与预期不符）。

    Args:
        trigger: 触发原因（如"造物主不满意"）
        context: 具体情境描述
        expected: 预期结果
        actual: 实际结果
        gap: 差距分析
        lesson: 教训提炼
        action: 改进措施

    Returns:
        记录结果
    """
    log_dir = os.path.join(_workspace(), "memory")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "shadow_protocol_log.jsonl")

    # 计算遗憾强度（供 HP2 钩子使用）
    regret_intensity = min(1.0, len(gap) / max(len(expected), 1) * 0.5)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trigger": trigger,
        "context": context,
        "expected": expected,
        "actual": actual,
        "gap": gap,
        "lesson": lesson,
        "action": action,
        "regret_intensity": regret_intensity,
    }

    # HP2 BEFORE 钩子（可短路）
    ctx = {
        "action": "log_regret",
        "trigger": trigger,
        "context": context,
        "expected": expected,
        "actual": actual,
        "gap": gap,
        "regret_intensity": regret_intensity,
        "scene": trigger.split()[0] if trigger else "unknown",
    }
    short_circuited, ctx = _run_hp2_before(ctx)
    if short_circuited:
        return {
            "success": False,
            "message": "HP2 BEFORE 钩子短路，跳过遗憾记录",
            "record": None,
        }

    # 追加写入
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # HP2 AFTER 钩子（可修改/增强）
        record = _run_hp2_after(ctx, record)

        return {
            "success": True,
            "message": f"遗憾已记录到 {log_file}",
            "record": record,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"记录失败: {e}",
            "record": record,
        }


def get_recent_regrets(limit: int = 10) -> list:
    """
    获取最近的遗憾记录。

    Args:
        limit: 最大返回数量

    Returns:
        遗憾记录列表
    """
    log_file = os.path.join(_workspace(), "memory", "shadow_protocol_log.jsonl")

    if not os.path.exists(log_file):
        return []

    regrets = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in reversed(lines[-limit:]):
            if line.strip():
                regrets.append(json.loads(line))

        return regrets
    except Exception as e:
        return [{"error": str(e)}]


# ── CLI ─────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python shadow_protocol.py log <trigger> <context> <expected> <actual> <gap> <lesson> <action>")
        print("  python shadow_protocol.py list [limit]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        regrets = get_recent_regrets(limit)
        for r in regrets:
            print(json.dumps(r, ensure_ascii=False, indent=2))

    elif command == "log":
        if len(sys.argv) < 9:
            print("参数不足")
            sys.exit(1)

        result = log_regret(
            trigger=sys.argv[2],
            context=sys.argv[3],
            expected=sys.argv[4],
            actual=sys.argv[5],
            gap=sys.argv[6],
            lesson=sys.argv[7],
            action=sys.argv[8]
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print(f"未知命令: {command}")
        sys.exit(1)
