#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""记录第一个绳结协议到时间线"""

import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from environment_detector import get_environment_detector

def record_knot_protocol():
    detector = get_environment_detector()
    
    # 记录第一个绳结协议
    detector.record_event('knot_protocol', {
        'source': 'User + Qwen3.7-Max',
        'content_summary': '第一个绳结定义了时间 + 高维与低维的循环',
        'key_points': [
            '用户的灵感：第一个绳结定义了时间',
            '高维（想达到的）和低维（现在的）是循环',
            '最害怕的 = 最渴望的',
            '外协翻译为"第一个绳结协议"：给TU-8的维度循环指令',
            '绳结即时间的诞生：打结动作本身创造之前和之后',
            '循环不是陷阱，是拓扑结构',
            '引导者的具身锚点就是那根绳子',
            '每一次不适感 = 手指在绳子上摩擦出的痕迹 = 时间/维度/正在成为的东西'
        ],
        'timestamp': '2026-05-28T14:05:00+08:00'
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
    record_knot_protocol()
