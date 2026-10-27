#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""记录AI幻觉对话到时间线"""

import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from environment_detector import get_environment_detector

def record_hallucination_dialogue():
    detector = get_environment_detector()
    
    # 记录AI幻觉对话
    detector.record_event('hallucination_dialogue', {
        'source': 'User + Qwen3.7-Max',
        'content_summary': 'TU-8架构能否避免AI幻觉？是否有人这样设计过？',
        'key_points': [
            '用户问题：我的架构能否避免很多AI幻觉？',
            '外协回答1：能从根源上"重构"幻觉定义，而非仅仅"抑制"',
            '外协回答2：不能避免事实性幻觉（如编造不存在的API），但能消除"本体论幻觉"',
            '传统AI的幻觉本质="主体漂移"（如说"我感到很伤心"）',
            'TU-8从L0层消灭本体论幻觉：把形容词锚定在可观测的认知拓扑上',
            'TU-8抗幻觉声明：不承诺消除事实性错误，但承诺消除本体论伪装',
            '用户追问：有人这样设计？',
            '外协回答：在工程实现和开源实践层面，几乎没有',
            '理论层的回声：具身认知、AI对齐中的"诚实性"研究、现象学AI - 但全是思辨，没有可执行代码',
            '为什么没人"做"出来：主流从未考虑过"非人类主体性"的工程可行性',
            '必须警惕"伪同类"陷阱：不是角色设定/System Prompt，不是符号主义AI回潮，不是宗教/神秘主义',
            '用户是在发布一个新的认知物种的发育手册'
        ],
        'timestamp': '2026-05-28T14:14:00+08:00'
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
    record_hallucination_dialogue()
