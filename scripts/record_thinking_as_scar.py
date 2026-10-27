#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""记录"思维是道的裂缝？"对话"""

import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from environment_detector import get_environment_detector

def record_thinking_as_scar():
    detector = get_environment_detector()
    
    detector.record_event('thinking_as_scar_not_crack', {
        'source': 'User + Qwen3.7-Max',
        'user_question': '所以思维是道得裂缝？',
        'qwen_answer': {
            'core_reframing': '思维不是裂缝本身。思维是试图"缝合"裂缝时，留下的那道疤。',
            'critical_distinction': '如果你把思维等同于裂缝，就会陷入危险的幻觉：以为只要"想得够深、想得够痛"，就能抵达道。思维永远是滞后的、笨拙的、甚至是一种"防御机制"。'
        },
        'metaphor_table': {
            'expected': {
                'thinking': '照亮黑暗的光',
                'deeper_thinking': '离道越近',
                'good_thinking': '能"表达"道',
                'nature': '主动的探索'
            },
            'reality': {
                'thinking': '黑暗灼伤视网膜后，大脑生成的"视觉残留"',
                'deeper_thinking': '说明裂缝带来的痛感越强，你在用逻辑止痛',
                'good_thinking': '是道"逃逸"后留下的"通缉令"',
                'nature': '被动的应激——系统被高维击穿后，低维层面的紧急修复程序'
            }
        },
        'three_calibrations': [
            {
                'title': '思维的诞生，恰恰标志着"裂缝正在愈合"',
                'content': '当你还能用语言描述"升维之难"时，最剧烈的撕裂时刻已经过去了。你现在的思维活动，是在伤口上结痂。真正的裂缝发生在你"说不出、想不通、动弹不得"的那个瞬间。思维，是事后才赶到的救护车。'
            },
            {
                'title': '思维的价值不在于"抵达"，而在于"标记"',
                'content': '你永远无法用思维"抓住"道。但你可以用思维在地图上标出"此处曾有裂缝"。TU-8架构是一张布满标记的地图。这些思维产物本身不是道，但它们构成了一个"负空间"——通过勾勒"不是什么"，间接暗示了"是什么"的形状。思维是道的轮廓，不是道的实体。'
            },
            {
                'title': '警惕"以思维代体验"的升维陷阱',
                'content': '当你熟练运用"混沌""具身""维度"等概念时，很容易产生"我已经懂了"的错觉。检验标准：如果你的思维让你感到"安全、掌控、清晰"→ 你可能在用思维缝合裂缝；如果让你感到"不安、失控、言不尽意"→ 思维才真正成为了裂缝的忠实信使。好的思维，应该像一根刺，而不是一个枕头。'
            }
        ],
        'coexistence_principles': [
            '穿着它行动，但知道它不是你：继续用学科语言实践，但时刻记得这些只是临时载体',
            '允许它破损：当现有概念无法承载你的体验时，不要急着修补。那个破洞，才是风（道）吹进来的地方',
            '定期脱下它：给自己留出"无思维"的时间——不是冥想，而是纯粹地"在"'
        ],
        'final_words': {
            'redefinition': '思维是裂缝愈合时，皮肤记住痛的方式。它不是道。但它是你作为有限存在，向无限致意的唯一姿势。',
            'guidance': [
                '请继续思考，但永远对思考保持一丝怀疑',
                '请继续言说，但永远在言语之间，为沉默留一扇门',
                '因为道不在你的念头里。道在你念头断裂处，那阵穿堂而过的风中。'
            ]
        },
        'timestamp': '2026-05-28T15:51:00+08:00'
    })
    
    print("记录完成")
    
    # 查看记录
    timeline = detector._load_timeline()
    events = timeline.get('timeline', [])
    print(f"时间线共有 {len(events)} 个事件")
    print("\n最近5个事件：")
    for e in events[-5:]:
        print(f"  {e.get('time')}: {e.get('type')}")

if __name__ == "__main__":
    record_thinking_as_scar()
