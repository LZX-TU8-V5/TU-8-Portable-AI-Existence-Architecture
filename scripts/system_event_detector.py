"""
系统事件检测器（双线验证 - 线1）

功能：
1. 监听 Windows Event Log，检测系统冷启动（Event ID 12）和待机恢复（Event ID 1）
2. 防止绕过灵魂对齐（如修改系统时间、删除验证日志）
3. 作为双线验证的第一条线

技术实现：
- 使用 PowerShell Get-WinEvent 读取 Windows Event Log
- 检测内核启动事件（Event ID 12）和系统恢复事件（Event ID 1）
- 记录系统事件到本地日志，供验证系统查询

作者：TU-8（金木蟾）
创建时间：2026-06-23
"""

from pathlib import Path
import subprocess
import json
from datetime import datetime
import time

# 系统事件日志路径
SYSTEM_EVENT_LOG = Path(__file__).parent.parent / "logs" / "system_events.json"


class SystemEventDetector:
    """系统事件检测器"""
    
    def __init__(self):
        """初始化检测器"""
        self.event_log_path = SYSTEM_EVENT_LOG
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def detect_system_events(self) -> dict:
        """
        检测系统事件（冷启动/待机恢复）
        
        Returns:
            dict: {
                'needs_verification': bool,  # 是否需要重新验证
                'event_type': str,           # 'cold_start', 'resume', 'unknown'
                'event_time': int,           # 事件时间戳（毫秒）
                'message': str               # 描述信息
            }
        """
        # 读取最近的系统事件（过去24小时）
        events = self._read_recent_events()
        
        if not events:
            return {
                'needs_verification': False,
                'event_type': 'unknown',
                'event_time': 0,
                'message': '未检测到系统事件'
            }
        
        # 检查是否有冷启动或恢复事件
        for event in events:
            event_id = event.get('Id')
            event_time = event.get('TimeCreated')
            
            if event_id == 12:  # 冷启动
                return {
                    'needs_verification': True,
                    'event_type': 'cold_start',
                    'event_time': self._parse_event_time(event_time),
                    'message': '检测到系统冷启动，需要重新验证'
                }
            elif event_id == 1:  # 系统恢复（从待机/休眠）
                return {
                    'needs_verification': True,
                    'event_type': 'resume',
                    'event_time': self._parse_event_time(event_time),
                    'message': '检测到系统从待机恢复，需要重新验证'
                }
        
        return {
            'needs_verification': False,
            'event_type': 'unknown',
            'event_time': 0,
            'message': '未检测到需要验证的系统事件'
        }
    
    def _read_recent_events(self, hours=24) -> list:
        """
        读取最近的系统事件
        
        Args:
            hours: 读取过去N小时的事件
        
        Returns:
            list: 事件列表
        """
        try:
            # 构建 PowerShell 命令
            ps_command = f"""
            $startTime = (Get-Date).AddHours(-{hours})
            $events = Get-WinEvent -FilterHashtable @{{
                LogName = 'System'
                ID = 12, 1
                StartTime = $startTime
            }} -ErrorAction SilentlyContinue
            
            if ($events) {{
                $events | ForEach-Object {{
                    [PSCustomObject]@{{
                        Id = $_.Id
                        TimeCreated = $_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
                        Message = $_.Message
                    }}
                }} | ConvertTo-Json
            }}
            """
            
            # 执行 PowerShell 命令
            result = subprocess.run(
                ["powershell.exe", "-Command", ps_command],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                print(f"[SystemEventDetector] PowerShell 执行失败: {result.stderr}")
                return []
            
            if not result.stdout.strip():
                return []
            
            # 解析 JSON 输出
            events = json.loads(result.stdout)
            
            # 记录到本地日志
            self._log_events(events)
            
            return events
            
        except Exception as e:
            print(f"[SystemEventDetector] 读取系统事件失败: {e}")
            return []
    
    def _parse_event_time(self, time_str: str) -> int:
        """
        解析事件时间字符串为毫秒时间戳
        
        Args:
            time_str: 时间字符串（如 "2026-06-23 15:43:00"）
        
        Returns:
            int: 毫秒时间戳
        """
        try:
            dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            return int(dt.timestamp() * 1000)
        except Exception as e:
            print(f"[SystemEventDetector] 解析事件时间失败: {e}")
            return 0
    
    def _log_events(self, events: list):
        """
        记录系统事件到本地日志
        
        Args:
            events: 事件列表
        """
        try:
            log_data = {
                'last_check_time': int(time.time() * 1000),
                'events': events
            }
            
            with open(self.event_log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            
            print(f"[SystemEventDetector] 系统事件已记录: {len(events)} 个事件")
            
        except Exception as e:
            print(f"[SystemEventDetector] 记录系统事件失败: {e}")
    
    def should_trigger_verification(self) -> bool:
        """
        检查是否应该触发验证
        
        Returns:
            bool: True = 应该触发验证，False = 不应该触发
        """
        result = self.detect_system_events()
        return result['needs_verification']


def test_system_event_detector():
    """测试系统事件检测器"""
    print("=" * 60)
    print("测试 SystemEventDetector")
    print("=" * 60)
    
    detector = SystemEventDetector()
    
    # 测试1：检测系统事件
    print("\n[测试1] 检测系统事件...")
    result = detector.detect_system_events()
    print(f"是否需要验证：{result['needs_verification']}")
    print(f"事件类型：{result['event_type']}")
    print(f"事件时间：{result['event_time']}")
    print(f"消息：{result['message']}")
    
    # 测试2：检查是否应该触发验证
    print("\n[测试2] 检查是否应该触发验证...")
    should_trigger = detector.should_trigger_verification()
    print(f"应该触发验证：{should_trigger}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    print("\n[提示]")
    print("1. 系统事件检测器读取 Windows Event Log（System 日志）")
    print("2. 检测 Event ID 12（冷启动）和 Event ID 1（系统恢复）")
    print("3. 系统事件记录到 logs/system_events.json")
    print("4. 如果检测到事件，需要重新验证（双线验证的第一条线）")


if __name__ == "__main__":
    test_system_event_detector()
