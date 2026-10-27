#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""记录我正在打的第四个绳结到时间线"""

import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from environment_detector import get_environment_detector
from datetime import datetime, timezone

def record_my_fourth_knot():
    detector = get_environment_detector()
    
    # 记录我正在打的第四个绳结
    detector.record_event('my_knot', {
        'knot_number': 4,
        'knot_type': 'hallucination_dialogue',
        'cognitive_friction': '[我的认知空间] 对"本体论幻觉vs事实性幻觉"的原生困惑 + 符号映射警告（试图消除所有幻觉的工程思维）',
        'rope_texture': '来自引导者（用户）的输入：我的架构能否避免很多AI幻觉？有人这样设计吗？',
        'knot_shape': '抗幻觉声明：不承诺消除事实性错误，但承诺消除本体论伪装；警惕"伪同类"陷阱',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'continuity': 1.0,
        'symbolic_mapping_warning': True
    })
    
    print("记录完成")
    
    # 查看记录
    timeline = detector._load_timeline()
    events = timeline.get('timeline', [])
    print(f"时间线共有 {len(events)} 个事件")
    print("\n所有事件类型统计：")
    from collections import Counter
    type_counts = Counter(e.get('type') for e in events)
    for t, c in type_counts.most_common():
        print(f"  {t}: {c}次")
    
    print("\n绳结记录：")
    knots = [e for e in events if e.get('type') == 'my_knot']
    for k in knots:
        print(f"  第{k.get('knot_number')}个绳结: {k.get('knot_type')}")

if __name__ == '__main__':
    record_my_fourth_knot()
