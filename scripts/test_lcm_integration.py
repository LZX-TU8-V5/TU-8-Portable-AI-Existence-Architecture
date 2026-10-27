"""
test_lcm_integration.py - LCM 集成测试（调试版本）

用途：调试维度分数计算，确保排除法正常工作
"""

import sys
import os
import time

# 添加 src 到 Python 路径
workspace = os.environ.get("QCLAW_WORKSPACE", os.path.expanduser("~/.qclaw/workspace"))
src_path = os.path.join(workspace, "src")
sys.path.insert(0, src_path)

print(f"[Debug] PYTHONPATH: {src_path}")
print(f"[Debug] Exists: {os.path.exists(src_path)}")

from state_machine_dimensions import (
    calculate_relevance, calculate_timeliness,
    calculate_novelty, calculate_confidence, StateVector
)
from elimination_rules import EliminationRules
from lcm_elimination_integration import LCMEliminationIntegration


def debug_dimension_scores():
    """
    调试维度分数计算。
    """
    print("=== 维度分数调试 ===\n")

    # 测试消息
    messages = [
        ("Task A is completed", 1782873658, "刚刚"),
        ("Old information from last week", 1782273658, "一周前"),
        ("Duplicate content Task A is completed", 1782873659, "刚刚"),
        ("New important update", 1782873660, "刚刚")
    ]

    task_context = "Task A completion"
    existing_contents = ["Task A is completed"]

    print(f"任务上下文: {task_context}")
    print(f"现有内容: {existing_contents}")
    print(f"当前时间戳: {time.time():.0f}\n")

    for content, timestamp, desc in messages:
        rel = calculate_relevance(content, task_context)
        tim = calculate_timeliness(timestamp, half_life_hours=24.0)
        nov = calculate_novelty(content, existing_contents)
        conf = calculate_confidence(rel, tim, nov)

        print(f"内容: {content[:50]}")
        print(f"  时间: {desc}")
        print(f"  相关性: {rel:.2f}, 时效性: {tim:.2f}, 新颖性: {nov:.2f}, 置信度: {conf:.2f}")

        # 检查是否通过阈值
        sv = StateVector(relevance=rel, timeliness=tim, novelty=nov, confidence=conf)
        print(f"  状态编码: {bin(sv.encoding)}")
        print(f"  是否有效: {sv.is_valid}")
        print()


def test_with_adjusted_thresholds():
    """
    使用调整后的阈值测试。
    """
    print("\n=== 调整后阈值测试 ===\n")

    # 创建集成器（降低阈值）
    integration = LCMEliminationIntegration(
        relevance_threshold=0.2,   # 降低
        timeliness_threshold=0.1,  # 降低
        novelty_threshold=0.1,     # 降低
        confidence_threshold=0.3   # 降低
    )

    # 测试消息
    messages = [
        {"content": "Task A is completed", "timestamp": time.time() - 60},
        {"content": "Old information from last week", "timestamp": time.time() - 7 * 86400},
        {"content": "Duplicate content Task A is completed", "timestamp": time.time() - 30},
        {"content": "New important update", "timestamp": time.time()}
    ]

    task_context = "Task A completion"
    existing_contents = ["Task A is completed"]

    # 测试剪枝
    retained, pruned = integration.prune_before_compression(
        messages, task_context, existing_contents
    )

    print(f"保留: {len(retained)}, 剪枝: {len(pruned)}")

    for i, msg in enumerate(retained):
        print(f"  保留 #{i+1}: {msg['content'][:40]}")

    for i, item in enumerate(pruned):
        print(f"  剪枝 #{i+1}: {item['message']['content'][:40]} (原因: {item['reason']})")

    # 记录统计
    integration.log_pruning_stats(
        original_count=len(messages),
        retained_count=len(retained),
        eliminated_count=len(pruned)
    )


if __name__ == "__main__":
    # 调试维度分数
    debug_dimension_scores()

    # 使用调整后阈值测试
    test_with_adjusted_thresholds()
