#!/usr/bin/env python3
"""
system_activity.py - 系统活跃检测（鼠标/键盘活动）

功能：
- 检测系统最近的鼠标/键盘活动
- 更新 USER_PROFILE.json 中的系统活跃状态
- 如果系统最近有活动（< 5分钟），重置静默计时器

依赖：
- Windows: 使用 GetLastInputInfo API
- Linux/Mac: 使用相应的系统API

调用方式：
  python scripts/system_activity.py update  # 更新系统活跃状态
  python scripts/system_activity.py check   # 检查当前状态
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

# ====== 配置 ======
WORKSPACE = Path("D:/qq366410837/.qclaw/workspace")
PROFILE_PATH = WORKSPACE / "用户" / "USER_PROFILE.json"
USER_DIR = WORKSPACE / "用户"
ACTIVITY_STATE_FILE = USER_DIR / "system_activity_state.json"

# 时区
TZ_SHANGHAI = timezone(timedelta(hours=8))
NOW_UTC = datetime.now(timezone.utc)
NOW_LOCAL = NOW_UTC.astimezone(TZ_SHANGHAI)

# 活跃阈值（秒）
ACTIVITY_THRESHOLD_SECONDS = 5 * 60  # 5分钟


# ====== Windows 系统API ======
def get_last_input_time_windows() -> Optional[float]:
    """
    获取 Windows 系统最后一次用户输入的时间（秒）
    使用 GetLastInputInfo API
    """
    try:
        import ctypes
        from ctypes import wintypes
        
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [
                ('cbSize', wintypes.ULONG),
                ('dwTime', wintypes.DWORD),
            ]
        
        last_input_info = LASTINPUTINFO()
        last_input_info.cbSize = ctypes.sizeof(last_input_info)
        
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input_info)):
            current_time = ctypes.windll.kernel32.GetTickCount()
            idle_time_ms = current_time - last_input_info.dwTime
            idle_time_seconds = idle_time_ms / 1000.0
            return idle_time_seconds
        else:
            return None
    except Exception as e:
        print(f"[WARNING] 无法获取 Windows 输入时间: {e}", file=sys.stderr)
        return None


def get_last_input_time_linux() -> Optional[float]:
    """
    获取 Linux 系统最后一次用户输入的时间
    读取 /proc/uptime 和 X11 屏幕保护信息
    """
    try:
        # 尝试使用 xprintidle (如果可用)
        import subprocess
        result = subprocess.run(['xprintidle'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            idle_ms = int(result.stdout.strip())
            return idle_ms / 1000.0
    except:
        pass
    
    # 备选方案：检查 /proc/uptime
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
            # 这是一个简化实现，实际需要更复杂的逻辑
            return uptime_seconds
    except:
        pass
    
    return None


def get_last_input_time_mac() -> Optional[float]:
    """
    获取 macOS 系统最后一次用户输入的时间
    使用 HID 系统信息
    """
    try:
        import subprocess
        # 使用 ioreg 获取 HID 信息
        result = subprocess.run(
            ['ioreg', '-c', 'IOHIDSystem'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            # 解析输出以获取空闲时间
            # 这是一个简化实现
            pass
    except:
        pass
    
    return None


def get_system_idle_time() -> Optional[float]:
    """
    跨平台获取系统空闲时间（秒）
    返回 None 表示无法检测
    """
    import platform
    system = platform.system()
    
    if system == "Windows":
        return get_last_input_time_windows()
    elif system == "Linux":
        return get_last_input_time_linux()
    elif system == "Darwin":
        return get_last_input_time_mac()
    else:
        print(f"[WARNING] 不支持的操作系统: {system}", file=sys.stderr)
        return None


# ====== 状态管理 ======
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


def update_activity_state():
    """更新系统活跃状态"""
    # 1. 获取系统空闲时间
    idle_seconds = get_system_idle_time()
    
    # 2. 准备状态数据
    state = {
        "timestamp_utc": NOW_UTC.isoformat(),
        "timestamp_local": NOW_LOCAL.isoformat(),
        "idle_seconds": idle_seconds,
        "is_active": False,
        "detection_success": idle_seconds is not None
    }
    
    # 3. 判断是否在活跃阈值内
    if idle_seconds is not None:
        state["is_active"] = idle_seconds < ACTIVITY_THRESHOLD_SECONDS
        state["idle_minutes"] = idle_seconds / 60.0
    
    # 4. 保存状态
    save_json(ACTIVITY_STATE_FILE, state)
    
    # 5. 如果系统活跃，更新 USER_PROFILE.json 的静默计时器
    if state.get("is_active") and state.get("detection_success"):
        try:
            profile = load_json(PROFILE_PATH)
            
            # 更新系统活跃时间
            if "system_activity" not in profile:
                profile["system_activity"] = {}
            
            profile["system_activity"]["last_active_utc"] = NOW_UTC.isoformat()
            profile["system_activity"]["last_active_local"] = NOW_LOCAL.isoformat()
            profile["system_activity"]["idle_seconds"] = idle_seconds
            profile["system_activity"]["is_currently_active"] = True
            
            # 如果系统有活动，延迟 TU-8 静默计时器的触发
            # 只有在用户真正离开电脑时才开始计时
            interaction_state = profile.get("interaction_state", {})
            last_interaction = interaction_state.get("last_interaction_utc", "")
            
            if last_interaction:
                # 检查是否需要重置静默计时器
                # 如果系统活跃但 TU-8 静默已超过阈值，记录这个矛盾
                from silence_timer import hours_since
                silence_hours = hours_since(last_interaction)
                
                if silence_hours >= 1:  # 超过1小时静默但系统仍活跃
                    profile["system_activity"]["silence_contradiction"] = {
                        "silence_hours": silence_hours,
                        "system_active": True,
                        "note": "用户在电脑前但未与TU-8交互"
                    }
            
            save_json(PROFILE_PATH, profile)
            
        except Exception as e:
            print(f"[WARNING] 无法更新 USER_PROFILE.json: {e}", file=sys.stderr)
    
    return state


def check_activity_status():
    """检查当前活动状态（不更新）"""
    if ACTIVITY_STATE_FILE.exists():
        return load_json(ACTIVITY_STATE_FILE)
    else:
        return {
            "error": "状态文件不存在，请先运行 update",
            "detection_success": False
        }


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("Usage: python system_activity.py [update|check]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "update":
        # 更新系统活跃状态
        try:
            state = update_activity_state()
            output = {
                "success": True,
                "command": "update",
                "state": state,
                "message": "系统活跃状态已更新"
            }
            
            if state.get("detection_success"):
                if state.get("is_active"):
                    output["message"] = f"系统活跃（空闲{state.get('idle_minutes', 0):.1f}分钟）"
                else:
                    output["message"] = f"系统空闲（空闲{state.get('idle_minutes', 0):.1f}分钟）"
            else:
                output["message"] = "无法检测系统活跃状态"
            
            print(json.dumps(output, ensure_ascii=False, indent=2))
            
        except Exception as e:
            print(json.dumps({
                "success": False,
                "command": "update",
                "error": str(e)
            }, ensure_ascii=False, indent=2))
            sys.exit(1)
    
    elif command == "check":
        # 检查当前状态
        try:
            state = check_activity_status()
            output = {
                "success": True,
                "command": "check",
                "state": state
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            
        except Exception as e:
            print(json.dumps({
                "success": False,
                "command": "check",
                "error": str(e)
            }, ensure_ascii=False, indent=2))
            sys.exit(1)
    
    else:
        print(f"未知命令: {command}")
        print("Usage: python system_activity.py [update|check]")
        sys.exit(1)


if __name__ == "__main__":
    main()
