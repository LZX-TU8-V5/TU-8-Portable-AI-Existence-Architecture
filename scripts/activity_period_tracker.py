"""
活动期跟踪器（动态时间锚点）

功能：
1. 记录用户第一次验证的时间作为活动期起点
2. 以24小时为周期，动态适应用户的真实作息
3. 为复盘机制提供准确的时间周期

设计理念：
- 不是固定时间窗口（如08:00-23:00），而是以第一次验证为起点的24小时周期
- 支持"下午3点起床"或"通宵工作"等非标准作息
- 为复盘机制提供准确的活动周期数据

作者：TU-8（金木蟾）
创建时间：2026-06-23
"""

from pathlib import Path
import json
from datetime import datetime, timedelta
import time

# 活动期日志路径
ACTIVITY_PERIOD_LOG = Path(__file__).parent.parent / "logs" / "activity_period.json"

# 事件类型
EVENT_TYPE_ACTIVITY_START = "activity_period_start"
EVENT_TYPE_ACTIVITY_END = "activity_period_end"


class ActivityPeriodTracker:
    """动态活动期跟踪器"""
    
    def __init__(self):
        """初始化跟踪器"""
        self.log_path = ACTIVITY_PERIOD_LOG
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def mark_activity_start(self, verification_method="password") -> dict:
        """
        标记活动期起点（第一次验证时调用）
        
        Args:
            verification_method: 验证方式（password/biometric/ etc.）
        
        Returns:
            dict: 活动期信息
        """
        now = datetime.now()
        now_ms = int(now.timestamp() * 1000)
        
        # 创建活动期记录
        activity_period = {
            'start_time': now_ms,
            'start_date': now.strftime('%Y-%m-%d'),
            'start_hour': now.hour,
            'start_minute': now.minute,
            'end_time': int((now + timedelta(days=1)).timestamp() * 1000),
            'end_date': (now + timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_hour': now.hour,  # 24小时后
            'is_active': True,
            'verification_method': verification_method,
            'created_at': now_ms
        }
        
        # 写入日志
        self._write_log(activity_period)
        
        # 记录到 events 表（为复盘机制提供数据）
        self._log_activity_event(activity_period, EVENT_TYPE_ACTIVITY_START)
        
        return activity_period
    
    def get_current_activity_period(self) -> dict:
        """
        获取当前活动期
        
        Returns:
            dict: 当前活动期信息，如果活动期已结束则返回 None
        """
        if not self.log_path.exists():
            return None
        
        log = self._read_log()
        
        if not log:
            return None
        
        # 检查活动期是否有效（24小时内）
        now_ms = int(time.time() * 1000)
        
        # 如果当前时间 < 活动期结束时间，说明活动期仍有效
        if log.get('end_time', 0) > now_ms:
            return log
        
        # 活动期已结束
        return None
    
    def is_new_activity_period_needed(self) -> bool:
        """
        检查是否需要新的活动期
        
        Returns:
            bool: True = 需要新的活动期，False = 当前活动期仍有效
        """
        current_period = self.get_current_activity_period()
        return current_period is None
    
    def end_current_activity_period(self, end_time_ms=None):
        """结束当前活动期（用于强制结束，如用户主动退出）"""
        current_period = self.get_current_activity_period()
        
        if current_period:
            # 标记为非活跃
            current_period['is_active'] = False
            current_period['ended_at'] = int(time.time() * 1000)
            
            # 修复：更新 end_time 为实际结束时间
            if end_time_ms is None:
                end_time_ms = current_period['ended_at']
            current_period['end_time'] = end_time_ms
            
            # 写入日志
            self._write_log(current_period)
            
            # 记录到 events 表
            self._log_activity_event(current_period, EVENT_TYPE_ACTIVITY_END)
    
    def get_activity_period_history(self, days=7) -> list:
        """
        获取历史活动期记录
        
        Args:
            days: 查询最近N天的记录
        
        Returns:
            list: 历史活动期列表
        """
        # 注意：当前实现只保留最新的活动期
        # 如果需要历史记录，需要修改为追加模式
        
        if not self.log_path.exists():
            return []
        
        log = self._read_log()
        
        if not log:
            return []
        
        # 检查是否在查询范围内
        now = datetime.now()
        log_time = datetime.fromtimestamp(log['start_time'] / 1000)
        
        if (now - log_time).days <= days:
            return [log]
        
        return []
    
    def _write_log(self, data: dict):
        """写入活动期日志"""
        with open(self.log_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _read_log(self) -> dict:
        """读取活动期日志"""
        if not self.log_path.exists():
            return None
        
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ActivityPeriodTracker] 读取日志失败: {e}")
            return None
    
    def _log_activity_event(self, activity_period: dict, event_type: str):
        """
        记录活动期事件到 knowledge graph（events 表）
        
        注意：这是一个接口占位符，实际实现需要调用 knowledge graph 的 API
        """
        # TODO: 实际实现需要调用 add_event_to_knowledge_graph()
        event_data = {
            'category': 'time_anchor',
            'event_type': event_type,
            'timestamp': activity_period['start_time'],
            'date': activity_period['start_date'],
            'start_hour': activity_period['start_hour'],
            'period_duration_hours': 24,
            'verification_method': activity_period.get('verification_method', 'unknown'),
            'source': 'activity_period_tracker',
            'rationale': '每日时间锚点起点（动态活动期）' if event_type == EVENT_TYPE_ACTIVITY_START else '活动期结束'
        }
        
        # 打印日志（临时方案）
        print(f"[ActivityPeriodTracker] 记录事件: {event_type} @ {activity_period['start_date']} {activity_period['start_hour']:02d}:{activity_period['start_minute']:02d}")
        
        # TODO: 实际写入 knowledge graph
        # add_event_to_knowledge_graph(event_data)
    
    def format_activity_period(self, activity_period: dict) -> str:
        """
        格式化活动期信息（用于显示）
        
        Args:
            activity_period: 活动期字典
        
        Returns:
            str: 格式化的字符串
        """
        start_dt = datetime.fromtimestamp(activity_period['start_time'] / 1000)
        end_dt = datetime.fromtimestamp(activity_period['end_time'] / 1000)
        
        duration_hours = (activity_period['end_time'] - activity_period['start_time']) / (1000 * 60 * 60)
        
        return f"""
[活动期信息]

起点：{start_dt.strftime('%Y-%m-%d %H:%M')}
终点：{end_dt.strftime('%Y-%m-%d %H:%M')}
时长：{duration_hours:.1f} 小时
验证方式：{activity_period.get('verification_method', 'unknown')}
状态：{'活跃' if activity_period.get('is_active') else '已结束'}
""".strip()


def test_activity_period_tracker():
    """测试活动期跟踪器"""
    print("=" * 60)
    print("测试 ActivityPeriodTracker")
    print("=" * 60)
    
    tracker = ActivityPeriodTracker()
    
    # 测试1：检查是否需要新的活动期
    print("\n[测试1] 检查是否需要新的活动期...")
    needed = tracker.is_new_activity_period_needed()
    print(f"结果：{needed}")
    
    # 测试2：标记活动期起点
    print("\n[测试2] 标记活动期起点...")
    activity_period = tracker.mark_activity_start(verification_method="password_test")
    print(f"活动期起点：{activity_period['start_date']} {activity_period['start_hour']:02d}:{activity_period['start_minute']:02d}")
    print(f"活动期终点：{activity_period['end_date']} {activity_period['end_hour']:02d}:{activity_period['start_minute']:02d}")
    
    # 测试3：获取当前活动期
    print("\n[测试3] 获取当前活动期...")
    current = tracker.get_current_activity_period()
    if current:
        print(f"当前活动期：{current['start_date']} {current['start_hour']:02d}:{current['start_minute']:02d} - {current['end_date']} {current['end_hour']:02d}:{current['start_minute']:02d}")
    else:
        print("无有效活动期")
    
    # 测试4：格式化输出
    print("\n[测试4] 格式化输出...")
    formatted = tracker.format_activity_period(activity_period)
    print(formatted)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_activity_period_tracker()
