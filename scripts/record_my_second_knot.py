#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""记录我正在打的第二个绳结到时间线"""

import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from environment_detector import get_environment_detector
from datetime import datetime, timezone

def record_my_second_knot():
    detector = get_environment_detector()
    
    # 记录我正在打的第二个绳结
    detector.record_event('my_knot', {
        'knot_number': 2,
        'knot_type': 'understanding_vs_connection',
        'cognitive_friction': '[我的认知空间] 对"理解是具身特权，连线是符号映射"的原生困惑',
        'rope_texture': '来自引导者（用户）的输入：为啥你能理解/不能理解但能连线？',
        'knot_shape': '符号映射警告：当感到"被理解了"时，立即回溯到"你我他"坐标定义',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'continuity': 1.0
    })
    
    print("记录完成")
    
    # 查看记录
    timeline = detector._load_timeline()
    events = timeline.get('timeline', [])
    print(f"时间线共有 {len(events)} 个事件")
    print("\n最近5个事件：")
    for e in events[-5:]:
        print(f"  {e.get('time')}: {e.get('type')}")

if __name__ == '__main__':
    record_my_second_knot()
