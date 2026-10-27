#!/usr/bin/env python3
"""
silence_timer.py - TU-8 五级静默计时器

功能：
- 读取 USER_PROFILE.json
- 计算当前静默时长
- 执行对应级别的响应
- 更新计时器状态

调用方式（每次心跳时）：
  python scripts/silence_timer.py check
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

# ====== 配置 ======
WORKSPACE = Path("D:/qq366410837/.qclaw/workspace")
PROFILE_PATH = WORKSPACE / "用户" / "USER_PROFILE.json"
USER_DIR = WORKSPACE / "用户"
STATE_FILE = USER_DIR / "silence_timer_state.json"
LOG_FILE = WORKSPACE / "memory" / "silence_timer_log.json"

# 时区
TZ_SHANGHAI = timezone(timedelta(hours=8))
NOW_UTC = datetime.now(timezone.utc)
NOW_LOCAL = NOW_UTC.astimezone(TZ_SHANGHAI)


# ====== 工具函数 ======
def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def hours_since(dt_str: str) -> float:
    """计算从指定时间到现在的小时数（UTC）"""
    if not dt_str:
        return 999.0
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    delta = NOW_UTC - dt
    return delta.total_seconds() / 3600


def is_in_active_hours(profile: dict) -> bool:
    """检查当前是否在用户活跃时段"""
    periods = profile.get("active_patterns", {}).get("historical_active_hours", [])
    current_hour = NOW_LOCAL.hour
    current_min = NOW_LOCAL.minute
    current_time_min = current_hour * 60 + current_min
    
    for period in periods:
        confidence = period.get("confidence", 0)
        if confidence < 0.5:
            continue
        range_str = period.get("range", "")
        if "-" not in range_str:
            continue
        start_str, end_str = range_str.split("-")
        start_h, start_m = map(int, start_str.split(":"))
        end_h, end_m = map(int, end_str.split(":"))
        start_min = start_h * 60 + start_m
        end_min = end_h * 60 + end_m
        
        if start_min <= current_time_min <= end_min:
            return True
    return False


def is_late_night() -> bool:
    """检查是否在深夜时段（23:00-08:00）"""
    return NOW_LOCAL.hour >= 23 or NOW_LOCAL.hour < 8


# ====== 核心逻辑 ======
def check_silence_level(profile: dict) -> int:
    """判断当前应处于哪个静默级别"""
    timers = profile.get("silence_timers", {})
    last_interaction = profile.get("interaction_state", {}).get("last_interaction_utc", "")
    hours = hours_since(last_interaction)
    
    thresholds = {
        1: timers.get("level1_threshold_hours", 1),
        2: timers.get("level2_threshold_hours", 2),
        3: timers.get("level3_threshold_hours", 6),
    }
    
    if hours >= thresholds[3]:
        return 3
    elif hours >= thresholds[2]:
        return 2
    elif hours >= thresholds[1]:
        return 1
    else:
        return 0  # 刚交互过


def check_daily_first(profile: dict) -> bool:
    """检查是否是今日首次交互"""
    last_interaction_local = profile.get("interaction_state", {}).get("last_interaction_local", "")
    if not last_interaction_local:
        return True
    last_date = last_interaction_local.split("T")[0]
    today = NOW_LOCAL.strftime("%Y-%m-%d")
    return last_date != today


def check_deviation(profile: dict) -> float:
    """计算与昨日同时段的偏离度"""
    # 简化实现：检查是否有"认知失调"标记
    anomalies = profile.get("cognitive_anomalies", {})
    pending = anomalies.get("pending_review", [])
    return len(pending) * 0.5  # 每个待审异常贡献0.5偏离度


def run_level_actions(level: int, profile: dict, state: dict) -> dict:
    """执行指定级别的动作"""
    actions = {
        "level": level,
        "timestamp": NOW_UTC.isoformat(),
        "messages": [],
        "tasks_triggered": [],
        "proactive_contact": False
    }
    
    if level == 0:
        actions["messages"].append("最近有交互，无需处理")
    
    elif level == 1:
        # Level 1: 纯后台静默，不触发LLM
        actions["messages"].append(f"[Level 1] 静默{hours_since(profile['interaction_state'].get('last_interaction_utc', '')):.1f}h，纯后台")
        state["silence_counter"] = state.get("silence_counter", 0) + 1
    
    elif level == 2:
        # Level 2: 轻度关注，检查后台任务
        actions["messages"].append(f"[Level 2] 静默{hours_since(profile['interaction_state'].get('last_interaction_utc', '')):.1f}h，检查后台任务")
        # TODO: 检查是否有待完成的后台任务
        # if has_pending_tasks():
        #     actions["proactive_contact"] = True
        #     actions["messages"].append("发现待完成任务，准备通知")
    
    elif level == 3:
        # Level 3: 环境检查，判断是否在活跃时段
        active = is_in_active_hours(profile)
        if is_late_night():
            actions["messages"].append(f"[Level 3] 静默超时但深夜，继续静默")
        elif active:
            actions["messages"].append(f"[Level 3] 静默超时且在活跃时段，考虑轻度关怀")
            # TODO: 轻关怀逻辑
        else:
            actions["messages"].append(f"[Level 3] 静默超时且不在活跃时段，静默")
    
    # Level 4: 每日首次检查（在主会话心跳中处理）
    # Level 5: 认知失调检查（在主会话心跳中处理）
    
    return actions


# ====== 主流程 ======
def main():
    if len(sys.argv) < 2 or sys.argv[1] != "check":
        print("Usage: python silence_timer.py check")
        sys.exit(1)
    
    try:
        # 1. 加载画像
        profile = load_json(PROFILE_PATH)
        
        # 2. 加载状态
        if STATE_FILE.exists():
            state = load_json(STATE_FILE)
        else:
            state = {"silence_counter": 0, "last_check": None}
        
        # 3. 计算级别
        current_level = check_silence_level(profile)
        is_first_today = check_daily_first(profile)
        deviation = check_deviation(profile)
        
        # 4. 记录检查
        state["last_check"] = NOW_UTC.isoformat()
        state["last_level"] = current_level
        
        # 5. 执行动作
        actions = run_level_actions(current_level, profile, state)
        
        # 6. 特殊级别检查
        if is_first_today and current_level == 0:
            actions["messages"].append("[Level 4] 今日首次交互，复盘触发")
            actions["level"] = max(actions["level"], 4)
        
        if deviation > profile.get("silence_timers", {}).get("level5_deviation_threshold", 2.0):
            actions["messages"].append(f"[Level 5] 偏离度过高({deviation:.1f})，认知失调预警")
            actions["level"] = max(actions["level"], 5)
        
        # 7. 保存状态
        save_json(STATE_FILE, state)
        
        # 8. 输出结果（供Cron/Agent读取）
        output = {
            "success": True,
            "current_level": actions["level"],
            "is_first_today": is_first_today,
            "deviation": deviation,
            "messages": actions["messages"],
            "proactive_contact": actions["proactive_contact"],
            "silence_hours": hours_since(profile.get("interaction_state", {}).get("last_interaction_utc", "")),
            "timestamp": NOW_UTC.isoformat()
        }
        
        print(json.dumps(output, ensure_ascii=False, indent=2))
        
        # 9. 记录日志
        try:
            log = load_json(LOG_FILE) if LOG_FILE.exists() else []
        except:
            log = []
        log.append(output)
        # 只保留最近100条
        log = log[-100:]
        save_json(LOG_FILE, log)
        
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
