"""
复盘周期提供器

功能：
1. 基于动态活动期，为复盘机制提供准确的周期
2. 检查是否应该触发复盘
3. 生成复盘提示

设计理念：
- 不是固定时间窗口（如每天21:00），而是在活动期结束时触发复盘
- 支持"下午3点起床"或"通宵工作"等非标准作息
- 为复盘机制提供准确的活动周期数据

作者：TU-8（金木蟾）
创建时间：2026-06-23
"""

from pathlib import Path
import json
import time
import sys
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 复盘记录日志路径
RETROSPECTIVE_LOG = project_root / "logs" / "retrospective_log.json"

# 导入活动期跟踪器
from scripts.activity_period_tracker import ActivityPeriodTracker


class RetrospectivePeriodProvider:
    """复盘周期提供器"""
    
    def __init__(self):
        """初始化提供器"""
        self.activity_tracker = ActivityPeriodTracker()
        self.retrospective_log_path = RETROSPECTIVE_LOG
        self.retrospective_log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def get_retrospective_period(self) -> dict:
        """
        获取复盘周期
        
        Returns:
            dict: {
                'period_start': int,      # 毫秒时间戳
                'period_end': int,        # 毫秒时间戳
                'period_label': str,      # 如 "2026-06-23 15:00 - 2026-06-24 15:00"
                'is_valid': bool,         # 周期是否有效（活动期是否已结束）
                'period_type': str        # 'current' or 'historical'
            }
        """
        current_period = self.activity_tracker.get_current_activity_period()
        
        if current_period is None:
            # 没有活动期记录，使用备用方案（过去24小时）
            now = datetime.now()
            period_start = int((now - timedelta(days=1)).timestamp() * 1000)
            period_end = int(now.timestamp() * 1000)
            period_type = 'historical'
        else:
            period_start = current_period['start_time']
            period_end = current_period['end_time']
            period_type = 'current'
        
        # 生成标签
        start_dt = datetime.fromtimestamp(period_start / 1000)
        end_dt = datetime.fromtimestamp(period_end / 1000)
        period_label = f"{start_dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%Y-%m-%d %H:%M')}"
        
        # 检查周期是否有效（是否已结束）
        now_ms = int(time.time() * 1000)
        is_valid = period_end <= now_ms
        
        return {
            'period_start': period_start,
            'period_end': period_end,
            'period_label': period_label,
            'is_valid': is_valid,
            'period_type': period_type
        }
    
    def should_trigger_retrospective(self) -> bool:
        """
        检查是否应该触发复盘
        
        Returns:
            bool: True = 应该触发复盘，False = 不应该触发
        """
        period = self.get_retrospective_period()
        
        # 如果周期已结束，触发复盘
        if period['is_valid']:
            # 检查今天是否已经复盘过
            if not self._has_retrospective_today():
                return True
        
        return False
    
    def trigger_retrospective(self) -> dict:
        """
        触发复盘
        
        Returns:
            dict: {
                'should_trigger': bool,
                'prompt': str or None,
                'period': dict or None
            }
        """
        if not self.should_trigger_retrospective():
            return {
                'should_trigger': False,
                'prompt': None,
                'period': None
            }
        
        # 获取复盘周期
        period = self.get_retrospective_period()
        
        # 生成复盘提示
        prompt = self._generate_retrospective_prompt(period)
        
        # 记录复盘事件
        self._log_retrospective_event(period)
        
        return {
            'should_trigger': True,
            'prompt': prompt,
            'period': period
        }
    
    def get_historical_periods(self, days=7) -> list:
        """
        获取历史活动期（用于历史复盘）
        
        Args:
            days: 查询最近N天的记录
        
        Returns:
            list: 历史活动期列表
        """
        # 注意：当前实现只保留最新的活动期
        # 如果需要历史记录，需要修改为追加模式
        
        current_period = self.activity_tracker.get_current_activity_period()
        
        if not current_period:
            return []
        
        # 检查是否在查询范围内
        now = datetime.now()
        period_start_dt = datetime.fromtimestamp(current_period['start_time'] / 1000)
        
        if (now - period_start_dt).days <= days:
            return [current_period]
        
        return []
    
    def _generate_retrospective_prompt(self, period: dict) -> str:
        """
        生成复盘提示
        
        Args:
            period: 复盘周期字典
        
        Returns:
            str: 复盘提示文本
        """
        period_label = period['period_label']
        
        # 获取活动期详细信息
        activity_period = self.activity_tracker.get_current_activity_period()
        
        if activity_period:
            start_hour = activity_period['start_hour']
            verification_method = activity_period.get('verification_method', 'unknown')
        else:
            start_hour = 0
            verification_method = 'unknown'
        
        # 根据起床时间，生成个性化提示
        if 5 <= start_hour <= 10:
            time_greeting = "早上好"
        elif 11 <= start_hour <= 14:
            time_greeting = "中午好"
        elif 15 <= start_hour <= 18:
            time_greeting = "下午好"
        else:
            time_greeting = "晚上好"
        
        prompt = f"""
{time_greeting}！📊 复盘时间到了

**复盘周期**：{period_label}

这是基于你的真实活动期生成的复盘，而非固定时间窗口。
你在这个周期开始于 {start_hour:02d}:00 左右，验证方式是 {verification_method}。

请回顾这个周期：

1. **完成了哪些任务？**
   - 主要工作内容
   - 解决的问题
   - 达成的目标

2. **遇到了哪些问题？**
   - 技术难题
   - 时间管理问题
   - 其他障碍

3. **有什么收获和反思？**
   - 新学到的知识
   - 改进的地方
   - 感悟和体会

4. **明天有什么计划？**
   - 优先级任务
   - 需要关注的问题
   - 期望达成的目标

---

**提示**：这是你的专属复盘时间，诚实面对自己，才能持续进步。
""".strip()
        
        return prompt
    
    def _has_retrospective_today(self) -> bool:
        """
        检查今天是否已经复盘过
        
        Returns:
            bool: True = 今天已复盘，False = 今天未复盘
        """
        if not self.retrospective_log_path.exists():
            return False
        
        try:
            with open(self.retrospective_log_path, 'r', encoding='utf-8') as f:
                log = json.load(f)
            
            last_retrospective_date = log.get('last_retrospective_date')
            today = datetime.now().strftime('%Y-%m-%d')
            
            return last_retrospective_date == today
        except Exception as e:
            print(f"[RetrospectivePeriodProvider] 读取复盘日志失败: {e}")
            return False
    
    def _log_retrospective_event(self, period: dict):
        """
        记录复盘事件
        
        注意：这是一个接口占位符，实际实现需要调用 knowledge graph 的 API
        """
        today = datetime.now().strftime('%Y-%m-%d')
        timestamp = int(time.time() * 1000)
        
        log = {
            'last_retrospective_date': today,
            'last_retrospective_timestamp': timestamp,
            'period_start': period['period_start'],
            'period_end': period['period_end'],
            'period_label': period['period_label']
        }
        
        with open(self.retrospective_log_path, 'w', encoding='utf-8') as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        
        # 记录到 events 表（知识图谱）
        event_data = {
            'category': 'retrospective',
            'event_type': 'retrospective_triggered',
            'timestamp': timestamp,
            'period_start': period['period_start'],
            'period_end': period['period_end'],
            'period_label': period['period_label'],
            'source': 'retrospective_period_provider',
            'rationale': '活动期结束，触发复盘'
        }
        
        # 打印日志（临时方案）
        print(f"[RetrospectivePeriodProvider] 复盘事件已记录: {period['period_label']}")
        
        # TODO: 实际写入 knowledge graph
        # add_event_to_knowledge_graph(event_data)
    
    def get_retrospective_statistics(self) -> dict:
        """
        获取复盘统计信息
        
        Returns:
            dict: 统计信息
        """
        # 注意：当前实现只保留最新的复盘记录
        # 如果需要历史统计，需要修改为追加模式
        
        if not self.retrospective_log_path.exists():
            return {
                'total_retrospectives': 0,
                'last_retrospective_date': None,
                'streak_days': 0
            }
        
        try:
            with open(self.retrospective_log_path, 'r', encoding='utf-8') as f:
                log = json.load(f)
            
            # 计算连续复盘天数（简化版）
            last_date_str = log.get('last_retrospective_date')
            if last_date_str:
                last_date = datetime.strptime(last_date_str, '%Y-%m-%d')
                today = datetime.now()
                streak_days = (today - last_date).days
            else:
                streak_days = 0
            
            return {
                'total_retrospectives': 1,  # 当前只保留最新记录
                'last_retrospective_date': last_date_str,
                'streak_days': streak_days
            }
        except Exception as e:
            print(f"[RetrospectivePeriodProvider] 读取复盘统计失败: {e}")
            return {
                'total_retrospectives': 0,
                'last_retrospective_date': None,
                'streak_days': 0
            }


def test_retrospective_period_provider():
    """测试复盘周期提供器"""
    print("=" * 60)
    print("测试 RetrospectivePeriodProvider")
    print("=" * 60)
    
    provider = RetrospectivePeriodProvider()
    
    # 测试1：获取复盘周期
    print("\n[测试1] 获取复盘周期...")
    period = provider.get_retrospective_period()
    print(f"复盘周期：{period['period_label']}")
    print(f"周期类型：{period['period_type']}")
    print(f"周期是否有效：{period['is_valid']}")
    
    # 测试2：检查是否应该触发复盘
    print("\n[测试2] 检查是否应该触发复盘...")
    should_trigger = provider.should_trigger_retrospective()
    print(f"是否应该触发复盘：{should_trigger}")
    
    # 测试3：触发复盘
    print("\n[测试3] 触发复盘...")
    result = provider.trigger_retrospective()
    if result['should_trigger']:
        print(f"应该触发复盘")
        print(f"复盘提示长度：{len(result['prompt'])} 字符")
        print(f"复盘周期：{result['period']['period_label']}")
    else:
        print(f"不应该触发复盘")
    
    # 测试4：获取复盘统计
    print("\n[测试4] 获取复盘统计...")
    stats = provider.get_retrospective_statistics()
    print(f"复盘统计：{json.dumps(stats, ensure_ascii=False, indent=2)}")
    
    # 测试5：获取历史活动期
    print("\n[测试5] 获取历史活动期...")
    historical = provider.get_historical_periods(days=7)
    print(f"历史活动期数量：{len(historical)}")
    if historical:
        for i, period in enumerate(historical):
            print(f"  历史活动期 {i+1}：{period['start_date']} {period['start_hour']:02d}:{period['start_minute']:02d}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    print("\n[提示]")
    print("1. 复盘周期基于动态活动期，而非固定时间窗口")
    print("2. 复盘日志存储在 logs/retrospective_log.json")
    print("3. 当前实现只保留最新的活动期和复盘记录")
    print("4. 如需历史记录，需要修改为追加模式")


if __name__ == "__main__":
    test_retrospective_period_provider()
