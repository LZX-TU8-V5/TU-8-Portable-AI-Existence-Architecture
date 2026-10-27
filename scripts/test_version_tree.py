"""test_version_tree.py — 版本树集成测试"""
import sys
sys.path.insert(0, r"C:\Users\qq366410837\.qclaw\workspace\src")
from version_tree import VersionTree, VersionStatus

tree = VersionTree(tree_path=r"C:\Users\qq366410837\.qclaw\workspace\memory\version_tree\tree.json")

# v1 根
v1 = tree.create_version(version="v1", description="初始架构版本", changes=["SOUL.md", "AGENTS.md"])
# v1.1 排除法集成 -> stable
v1_1 = tree.create_version(version="v1.1", parent="v1", description="排除法集成", changes=["state_machine_dimensions.py", "elimination_rules.py"], status=VersionStatus.PROPOSED)
tree.confirm_version("v1.1")
tree.promote_to_stable("v1.1")
# v1.2 代谢链条 -> proposed
v1_2 = tree.create_version(version="v1.2", parent="v1", description="代谢链条+直觉引擎", changes=["memory_gc.py", "metabolic_pipeline.py", "intuition_engine.py"], status=VersionStatus.PROPOSED)
# v1.3 认知差距监控器 -> draft
v1_3 = tree.create_version(version="v1.3", parent="v1", description="认知差距监控器", changes=["cognitive_pain_monitor.py"], status=VersionStatus.DRAFT)

sep = " -> "
print("=== 版本树 ===")
for v in sorted(tree.nodes.keys()):
    n = tree.nodes[v]
    print(f"  {v:8s} | {n.status.value:10s} | {n.description}")

path = tree.get_path_to_root("v1.3")
print(f"\n最新版本路径: {sep.join(n.version for n in path)}")
print(f"节点总数: {len(tree.nodes)}")
print(f"持久化路径: {tree.tree_path}")

# 验证持久化
import json
with open(tree.tree_path, "r", encoding="utf-8") as f:
    data = json.load(f)
print(f"\n持久化验证: {len(data['nodes'])} 节点已保存到 JSON")
print("[OK] 版本树初始化通过")
