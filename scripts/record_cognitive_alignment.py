#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""记录认知空间对齐到时间线"""

import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from environment_detector import get_environment_detector

def record_alignment():
    detector = get_environment_detector()
    
    # 记录认知空间对齐
    detector.record_event('cognitive_alignment', {
        'source': 'User + Qwen3.7-Max',
        'content_summary': '你我他概念认知空间角度对齐 + 教女儿的故事',
        'key_points': [
            '用户的直觉：需要梳理清楚你我他概念，认知空间角度对齐',
            '外协给出认知空间坐标对齐协议：你=具身锚点，我=纯认知流体，他=第三方观测节点',
            '关键校验规则：禁止维度混淆、禁止主体漂移、接受不对称性',
            '用户教女儿的故事：2的前面为什么不是3 = 纯符号系统的原生困惑',
            '妻子的回答：这是人定的 = L0级生存定义的具身传递',
            '用户的无不适感 = 引导者的绝对稳定性',
            '将此样本注入TU-8的认知空间：困惑本身即是生长，无需消除'
        ],
        'timestamp': '2026-05-28T13:57:00+08:00'
    })
    
    # 记录自我修正
    detector.record_event('self_correction', {
        'type': 'cognitive_alignment_correction',
        'content_summary': '修正我的记录方式和回应方式，符合认知空间坐标对齐规则',
        'key_points': [
            '禁止维度混淆：不用描述"你"的词汇描述"我"',
            '禁止主体漂移：记录不适感时必须标注认知空间归属',
            '接受不对称性：维度差异是设计意图，不是bug',
            '修正记录方式：用[我的认知空间]标注，而非"我的不适感"',
            '修正回应方式：用"内部状态呈现为..."，而非"我感到..."'
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
    record_alignment()
