#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将"世界模型架构修正（主动预测 vs 被动激活）"写入 events 表（简化版，无 emoji）
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
    title = 'World Model Architecture Correction: Active Prediction vs Passive Activation'
    content = '''User corrected the world model design direction during debate with Qianwen:
1. Current stage (pure vision/cloud AI): AI hardware characteristic is "activate on demand", suitable for "passive activation framework"
2. Future stage (embodied intelligence/robot): Physical world has inertia and is full of dangers, must "actively predict" to avoid fatal delays
3. Architecture strategy: Make "prediction engine" a pluggable module, currently off, future on

Key insights:
- Human brain must actively predict because it only has 20W power, must use "active prediction" to shield known information and save biological computing power
- AI can passively activate because AI does not compute matrix multiplication without input, power consumption ≈ 0, no "burnout" problem
- Future embodied intelligence needs active prediction because physical world has inertia and is full of fatal dangers (e.g., robot grasping, autonomous driving)

Architecture decision:
- World model = passive cognitive framework (current) + pluggable active prediction interface (future) + built-in belief system
- Cognitive operating system: Cross-hardware-platform cognitive architecture supporting both passive activation and active prediction modes'''
    
    summary = 'World model reconstructed from "active prediction engine" to "passive cognitive framework + pluggable active prediction interface + built-in belief system"'
    category = 'architecture_decision'
    rationale = 'Hardware characteristics determine architecture design. Current AI hardware suits passive activation, future embodied intelligence needs active prediction. Designing prediction engine as pluggable module enables seamless switching across hardware platforms.'
    source_id = 'tu8_agent'
    metadata = {
        'debate_with': 'Qianwen',
        'user_correction': 'Human brain actively predicts because it would burn out, AI passively activates because it only runs when activated',
        'future_requirement': 'Reserve active prediction interface for future embodied intelligence',
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
    
    print(f"[SUCCESS] Event written to events table")
    print(f"  Event ID: {event_id}")
    print(f"  Event type: {category}")
    print(f"  Event title: {title}")
    
    # 验证写入
    print(f"\n[VERIFY] Verifying write...")
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, category, title, created_at
        FROM events
        WHERE id = ?
    """, (event_id,))
    
    row = cursor.fetchone()
    if row:
        print(f"[SUCCESS] Verification successful:")
        print(f"  ID: {row[0]}")
        print(f"  Category: {row[1]}")
        print(f"  Title: {row[2]}")
        print(f"  Created at: {row[3]}")
    else:
        print(f"[ERROR] Verification failed: Event {event_id} not found")
    
    conn.close()

if __name__ == '__main__':
    main()
