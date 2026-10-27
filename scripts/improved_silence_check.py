#!/usr/bin/env python3
"""
improved_silence_check.py - 改进版静默检测流程

功能：
1. 运行系统活跃检测（区分真静默 vs 只是不在对话窗口）
2. 运行静默计时器（读取更新后的状态）
3. 根据等级判断是否需要主动关怀
4. 写入或删除 pending_care.json

调用方式：
  python scripts/improved_silence_check.py
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ====== 配置 ======
WORKSPACE = Path("D:/qq366410837/.qclaw/workspace")
PROFILE_PATH = WORKSPACE / "用户" / "USER_PROFILE.json"
USER_DIR = WORKSPACE / "用户"
PENDING_CARE_FILE = USER_DIR / "pending_care.json"
SILENCE_LOG = WORKSPACE / "memory" / "improved_silence_check_log.json"

# 时区
TZ_SHANGHAI = timezone(timedelta(hours=8))
NOW_UTC = datetime.now(timezone.utc)
NOW_LOCAL = NOW_UTC.astimezone(TZ_SHANGHAI)


# ====== 工具函数 ======
def load_json(path: Path) -> dict:
    """加载 JSON 文件"""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict):
    """保存 JSON 文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_script(script_name: str, args: list) -> dict:
    """
    运行 Python 脚本并返回 JSON 输出
    """
    import sys
    python_exe = sys.executable
    
    cmd = [python_exe, str(WORKSPACE / "scripts" / script_name)] + args
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(WORKSPACE)
        )
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr,
                "stdout": result.stdout
            }
        
        # 尝试解析 JSON 输出
        output = result.stdout.strip()
        if not output:
            return {"success": False, "error": "空输出"}
        
        return json.loads(output)
        
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "脚本执行超时"}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON解析失败: {e}", "stdout": result.stdout}
    except Exception as e:
        return {"success": False, "error": str(e)}


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


def determine_care_level(silence_result: dict, activity_state: dict, profile: dict) -> dict:
    """
    根据静默检测结果和系统活跃状态，确定是否需要关怀及关怀等级
    
    返回：
    {
        "need_care": bool,
        "level": int,
        "reason": str,
        "message": str
    }
    """
    current_level = silence_result.get("current_level", 0)
    silence_hours = silence_result.get("silence_hours", 0)
    is_first_today = silence_result.get("is_first_today", False)
    deviation = silence_result.get("deviation", 0)
    
    system_active = activity_state.get("is_active", False)
    detection_success = activity_state.get("detection_success", False)
    
    # 决策逻辑
    
    # 1. 如果系统检测失败，退回到原来的逻辑
    if not detection_success:
        return {
            "need_care": current_level >= 3,
            "level": current_level,
            "reason": "system_detection_failed",
            "message": f"无法检测系统状态，使用原有 Level {current_level} 逻辑"
        }
    
    # 2. 系统活跃但 TU-8 静默 -> 用户只是不在对话窗口
    if system_active and current_level >= 1:
        return {
            "need_care": False,
            "level": 0,  # 重置为 0，因为用户还在电脑前
            "reason": "system_active_but_not_talking",
            "message": f"系统在活跃（空闲{activity_state.get('idle_minutes', 0):.1f}分钟），但用户未与TU-8交互"
        }
    
    # 3. 系统空闲且 TU-8 静默 -> 真静默
    if not system_active and current_level >= 1:
        # 真静默，按照原等级处理
        
        if current_level == 1:
            # Level 1: 真静默，但时间短，无需操作
            return {
                "need_care": False,
                "level": 1,
                "reason": "true_silence_short",
                "message": f"真静默 {silence_hours:.1f} 小时，无需操作"
            }
        
        elif current_level == 2:
            # Level 2: 真静默中等，检查后台任务
            return {
                "need_care": False,  # 暂不主动，除非有后台任务
                "level": 2,
                "reason": "true_silence_medium",
                "message": f"真静默 {silence_hours:.1f} 小时，检查后台任务"
            }
        
        elif current_level == 3:
            # Level 3: 真静默较长，判断活跃时段
            if is_late_night():
                return {
                    "need_care": False,
                    "level": 3,
                    "reason": "true_silence_long_but_late_night",
                    "message": f"真静默 {silence_hours:.1f} 小时，但深夜时段，继续静默"
                }
            elif is_in_active_hours(profile):
                return {
                    "need_care": True,
                    "level": 3,
                    "reason": "true_silence_long_and_active_hours",
                    "message": f"真静默 {silence_hours:.1f} 小时，且在活跃时段，考虑轻度关怀"
                }
            else:
                return {
                    "need_care": False,
                    "level": 3,
                    "reason": "true_silence_long_but_not_active_hours",
                    "message": f"真静默 {silence_hours:.1f} 小时，但不在活跃时段，静默"
                }
        
        elif current_level >= 4 or is_first_today:
            # Level 4: 每日首次 or 长时间静默
            return {
                "need_care": True,
                "level": 4,
                "reason": "daily_first_or_long_silence",
                "message": f"今日首次交互 或 静默 {silence_hours:.1f} 小时，触发每日复盘"
            }
        
        elif deviation >= profile.get("silence_timers", {}).get("level5_deviation_threshold", 2.0):
            # Level 5: 认知失调
            return {
                "need_care": True,
                "level": 5,
                "reason": "cognitive_dissonance",
                "message": f"偏离度 {deviation:.1f}，认知失调预警"
            }
    
    # 4. 默认：无需关怀
    return {
        "need_care": False,
        "level": current_level,
        "reason": "default_no_care",
        "message": "无需主动关怀"
    }


def write_pending_care(care_decision: dict):
    """写入 pending_care.json"""
    pending_care = {
        "level": care_decision["level"],
        "trigger": care_decision["reason"],
        "message": care_decision["message"],
        "timestamp_utc": NOW_UTC.isoformat(),
        "timestamp_local": NOW_LOCAL.isoformat(),
        "delivered": False,
        "need_care": care_decision["need_care"],
        "decision_details": care_decision
    }
    
    save_json(PENDING_CARE_FILE, pending_care)
    return pending_care


def delete_pending_care():
    """删除 pending_care.json（如果存在）"""
    if PENDING_CARE_FILE.exists():
        PENDING_CARE_FILE.unlink()
        return True
    return False


def log_result(result: dict):
    """记录日志"""
    try:
        log = load_json(SILENCE_LOG)
        # 确保 log 是列表
        if not isinstance(log, list):
            log = []
    except:
        log = []
    
    log_entry = {
        "timestamp_utc": NOW_UTC.isoformat(),
        "timestamp_local": NOW_LOCAL.isoformat(),
        "result": result
    }
    
    log.append(log_entry)
    # 只保留最近100条
    log = log[-100:]
    save_json(SILENCE_LOG, log)


# ====== 主流程 ======
def main():
    """主函数"""
    try:
        # ====== 步骤 1: 系统活跃检测 ======
        print("[步骤 1/4] 运行系统活跃检测...", file=sys.stderr)
        activity_result = run_script("system_activity.py", ["update"])
        
        if not activity_result.get("success"):
            print(f"[WARNING] 系统活跃检测失败: {activity_result.get('error')}", file=sys.stderr)
            activity_state = {"is_active": False, "detection_success": False}
        else:
            activity_state = activity_result.get("state", {})
        
        print(f"  系统状态: {'活跃' if activity_state.get('is_active') else '空闲'} "
              f"(空闲{activity_state.get('idle_minutes', 0):.1f}分钟)", file=sys.stderr)
        
        # ====== 步骤 2: 静默计时器检查 ======
        print("[步骤 2/4] 运行静默计时器检查...", file=sys.stderr)
        silence_result = run_script("silence_timer.py", ["check"])
        
        if not silence_result.get("success"):
            raise Exception(f"静默计时器检查失败: {silence_result.get('error')}")
        
        print(f"  静默等级: Level {silence_result.get('current_level')}, "
              f"静默时长: {silence_result.get('silence_hours', 0):.1f}小时", file=sys.stderr)
        
        # ====== 步骤 3: 加载用户画像 ======
        print("[步骤 3/4] 加载用户画像...", file=sys.stderr)
        profile = load_json(PROFILE_PATH)
        
        # ====== 步骤 4: 决策是否需要关怀 ======
        print("[步骤 4/4] 决策是否需要关怀...", file=sys.stderr)
        care_decision = determine_care_level(silence_result, activity_state, profile)
        
        print(f"  决策结果: {'需要关怀' if care_decision['need_care'] else '无需关怀'} "
              f"(Level {care_decision['level']}, 原因: {care_decision['reason']})", file=sys.stderr)
        
        # ====== 步骤 5: 处理 pending_care.json ======
        if care_decision["need_care"]:
            # 需要关怀：写入 pending_care.json
            pending_care = write_pending_care(care_decision)
            action = "write_pending_care"
            print(f"  已写入 pending_care.json (Level {care_decision['level']})", file=sys.stderr)
        else:
            # 无需关怀：删除 pending_care.json
            deleted = delete_pending_care()
            action = "delete_pending_care" if deleted else "no_action"
            if deleted:
                print(f"  已删除 pending_care.json", file=sys.stderr)
            else:
                print(f"  pending_care.json 不存在，无需删除", file=sys.stderr)
        
        # ====== 输出结果 ======
        result = {
            "success": True,
            "timestamp_utc": NOW_UTC.isoformat(),
            "timestamp_local": NOW_LOCAL.isoformat(),
            "activity_state": activity_state,
            "silence_result": silence_result,
            "care_decision": care_decision,
            "action": action,
            "pending_care_file": str(PENDING_CARE_FILE) if care_decision["need_care"] else None
        }
        
        # 记录日志
        log_result(result)
        
        # 输出 JSON（供 Cron/Agent 读取）
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "timestamp_utc": NOW_UTC.isoformat()
        }
        print(json.dumps(error_result, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
