# inject_date_context.py — 开机日期上下文注入 + 新日期标记
# =============================================================================
# 用途：
#   1. 每次冷启动后（cold_start_gate 阶段）调用：注入当前日期
#   2. 每日 00:00 cron 调用：刷新日期并标记"新的一天"
#
# 写入文件：
#   - _agent_memory/boot_context.json     — 日期上下文（通用读取）
#   - _agent_memory/date_context_dirty.json — 脏标记（heartbeat 感知后清除）
#     dirty 存在 = 新的一天已注入，heartbeat 应执行"新一天注入流程"
#
# 脏标记格式：
#   { "dirty": true, "new_date": "2026-07-11", "written_at": 1783732800 }
# =============================================================================

import json
import time
from pathlib import Path
from datetime import datetime

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT_MEM = WORKSPACE / "_agent_memory"
BOOT_CONTEXT = AGENT_MEM / "boot_context.json"
DIRTY_MARKER = AGENT_MEM / "date_context_dirty.json"
BOOT_TS_FILE = AGENT_MEM / "boot_timestamp.json"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_last_boot() -> dict:
    if BOOT_CONTEXT.exists():
        try:
            return json.loads(BOOT_CONTEXT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def get_boot_timestamp() -> str | None:
    """读开机时间文件"""
    if not BOOT_TS_FILE.exists():
        return None
    try:
        data = json.loads(BOOT_TS_FILE.read_text(encoding="utf-8"))
        return str(data.get("boot_time", ""))[:10]
    except Exception:
        return None


def main():
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    day_of_week = DAYS[now.weekday()]

    last_boot = get_last_boot()
    last_date = last_boot.get("current_date", current_date)

    is_new_day = current_date != last_date
    if is_new_day:
        try:
            last_dt = datetime.strptime(last_date, "%Y-%m-%d")
            days_since = (now - last_dt).days
        except Exception:
            days_since = 1
    else:
        # 也检查开机时间文件（双重保险）
        boot_date = get_boot_timestamp()
        if boot_date and boot_date != current_date:
            is_new_day = True
            try:
                last_dt = datetime.strptime(boot_date, "%Y-%m-%d")
                days_since = (now - last_dt).days
            except Exception:
                days_since = 1
        else:
            days_since = 0

    ctx = {
        "current_date": current_date,
        "current_time": current_time,
        "day_of_week": day_of_week,
        "is_new_day": is_new_day,
        "days_since_last_boot": days_since,
        "last_boot_date": last_date,
        "injected_ts": time.time(),
    }

    AGENT_MEM.mkdir(parents=True, exist_ok=True)
    BOOT_CONTEXT.write_text(
        json.dumps(ctx, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # 如果是新的一天，写脏标记 → 触发 heartbeat 注入流程
    if is_new_day:
        dirty = {
            "dirty": True,
            "new_date": current_date,
            "day_of_week": day_of_week,
            "days_since": days_since,
            "written_at": time.time(),
        }
        DIRTY_MARKER.write_text(
            json.dumps(dirty, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"NEW DAY MARKER: {current_date} ({day_of_week}), {days_since} days since last")
    else:
        # 清除脏标记（防止陈旧残留）
        if DIRTY_MARKER.exists():
            DIRTY_MARKER.unlink()
        print(f"Boot: {current_date} {current_time} ({day_of_week})")

    return ctx


if __name__ == "__main__":
    main()
