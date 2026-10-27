"""
把 EFHV 架构对话记录写入 events 表（简化版，纯 ASCII）
"""
import sys
import os

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sag_lite_knowledge_graph import KnowledgeGraphDB

db = KnowledgeGraphDB(r"C:\Users\qq366410837\.qclaw\workspace\knowledge_graph.db")

# 事件内容摘要
event_content = """EFHV（排除优先分层验证）架构完整推导对话记录。

## 核心架构定义
- L0：几何轮廓排除（纯几何模板，语义盲）
- L1：生物/非生物特征排除
- L2：状态拓扑排除（完整/切开/异常结构）
- L3：语义确认
- L4：环境/物理一致性验证

## 关键突破
1. 排除优先思维：从"正向分类"转变为"层级排除"
2. 语义延迟：L0-L2不碰语义，只做排除
3. 错误归因清晰：排除失败 = 数据/定义/标定缺陷（可修复）
4. 双向筛选闭环：世界模型预测指导验证，验证结果修正预测
5. 动态精度分配：精度根据预测置信度动态调节

## 完整认知系统（六层）
1. 稳态感知（L0-L4排除漏斗）
2. 瞬态惊跳（模式B开放探索 + 回神协议）
3. 感知饱和（L5主动交互：捏/闻/咬）
4. 知识检索（一级对齐：现有资料匹配）
5. 类比锚定（二级过渡：差异描述向量）
6. 本体生成（三级重定义：自主扩展认知边界）

完整对话记录见文档：docs/efhv_architecture_dialogue.md
"""

# 添加事件
event_id = db.add_event(
    title="EFHV（排除优先分层验证）架构完整推导",
    content=event_content,
    summary="与千问对话推导出完整的排除漏斗架构，包含L0-L4分层定义、双向筛选闭环、瞬态处理、多模态扩展、未知事物调节系统",
    category="architecture_decision",
    keywords=["EFHV", "排除优先", "分层验证", "认知架构", "视觉认知", "硬件兼容性", "双向筛选", "未知事物调节"],
    rationale="为TU-8审计引擎提供认知架构基础，定义L0-L4排除漏斗与内脑架构的映射关系",
    source_id="tu8_agent",
    metadata={
        "dialogue_partner": "千问",
        "dialogue_date": "2026-06-23",
        "document_reference": r"C:\Users\qq366410837\.qclaw\workspace\docs\efhv_architecture_dialogue.md",
        "status": "完整推导完成，待实施"
    }
)

print("[OK] Event created successfully!")
print(f"Event ID: {event_id}")
print(f"Title: EFHV（排除优先分层验证）架构完整推导")
print(f"Category: architecture_decision")
print(f"Source: tu8_agent")

# 验证写入
events = db.search_events_by_fts("EFHV", top_k=5)
print(f"\n[OK] Verification: Found {len(events)} events matching 'EFHV'")
for evt in events:
    print(f"  - {evt['id']}: {evt['title']}")

db.close()
