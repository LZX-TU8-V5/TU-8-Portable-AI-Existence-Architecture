#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将"世界模型架构修正（主动预测 vs 被动激活）"写入 events 表
"""

import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sag_lite_knowledge_graph import KnowledgeGraphDB

def main():
    # 初始化数据库
    db_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_graph.db')
    db = KnowledgeGraphDB(db_path)
    
    # 事件数据
    title = '世界模型架构修正：主动预测 vs 被动激活'
    content = '''用户在与千问的辩论中，修正了世界模型的设计方向：
1. 当前阶段（纯视觉/云端 AI）：AI 硬件特性是"激活才运转"，适合设计为"被动激活框架"
2. 未来阶段（具身智能/机器人）：物理世界有惯性且充满危险，必须"主动预测"以避免致命延迟
3. 架构策略：将"预测引擎"做成可插拔模块，当前关闭，未来开启

关键洞察：
- 人脑必须主动预测，是因为人脑功耗只有 20W，必须靠"主动预测"来屏蔽已知信息，节省生物算力
- AI 可以被动激活，是因为 AI 没有输入就不算矩阵乘法，功耗 ≈ 0，不存在"烧机"问题
- 未来具身智能需要主动预测，是因为物理世界有惯性，且充满致命危险（如机器人抓握、自动驾驶）

架构决策：
- 世界模型 = 被动认知框架（当前） + 可插拔主动预测接口（未来） + 内置信念系统
- 认知操作系统：跨硬件平台的认知架构，支持被动激活和主动预测两种模式'''
    
    summary = '世界模型从"主动预测引擎"重构为"被动认知框架 + 可插拔主动预测接口 + 内置信念系统"'
    category = 'architecture_decision'
    rationale = '硬件特性决定架构设计。当前 AI 硬件适合被动激活，未来具身智能需要主动预测。将预测引擎设计为可插拔模块，实现跨硬件平台的无缝切换。'
    source_id = 'tu8_agent'
    metadata = {
        'debate_with': '千问',
        'user_correction': '人脑主动预测是因为会烧机，AI 被动激活是因为激活才运转',
        'future_requirement': '预留主动预测接口，未来具身需要',
        'related_docs': [
            'docs/world_model_redesign.md',
            'docs/active_vs_passive_world_model.md'
        ],
        'confidence': 0.95
    }
    
    # 插入事件
    event_id = db.add_event(
        title,
        content,
        summary=summary,
        category=category,
        rationale=rationale,
        source_id=source_id,
        metadata=metadata
    )
    
    print(f"✅ 事件已写入 events 表")
    print(f"   事件 ID: {event_id}")
    print(f"   事件类型: {event_data['event_type']}")
    print(f"   事件标题: {event_data['title']}")
    
    # 验证写入
    print(f"\n🔍 验证写入...")
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, event_type, title, created_at
        FROM events
        WHERE id = ?
    """, (event_id,))
    
    row = cursor.fetchone()
    if row:
        print(f"✅ 验证成功:")
        print(f"   ID: {row[0]}")
        print(f"   类型: {row[1]}")
        print(f"   标题: {row[2]}")
        print(f"   创建时间: {row[3]}")
    else:
        print(f"❌ 验证失败: 未找到事件 {event_id}")
    
    conn.close()

if __name__ == '__main__':
    main()
