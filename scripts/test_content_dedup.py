"""test_content_dedup.py — 内容去重单元测试（修正版）"""
import sys, os
sys.path.insert(0, r"C:\Users\qq366410837\.qclaw\workspace\src")
from memory_dedup import _character_trigrams, _jaccard, _split_sections, _extract_body

# ---- 1. trigram 基本测试 ----
t1 = _character_trigrams("感知受控幻觉")
t2 = _character_trigrams("感知是受控幻觉")
sim = _jaccard(t1, t2)
print("1. 相似 Jaccard: {:.2f} (应 > 0.5)".format(sim))
assert sim > 0.5, "相似内容应高"

t3 = _character_trigrams("今天天气怎么样")
sim2 = _jaccard(t1, t3)
print("2. 不相关 Jaccard: {:.2f} (应 < 0.2)".format(sim2))
assert sim2 < 0.2, "不相关应低"

# ---- 2. 模拟 MEMORY.md 内容重复测试 ----
test_md = """## 2016-07-01 核心成果
感知 = 受控幻觉（预测编码理论）
闭眼 = 模型切换过渡期

## 2016-07-03 感知理论
感知本质是受控幻觉
预测编码理论的核心公式是感知=预测+误差
"""

sections = _split_sections(test_md)
print("3. 模拟段落: {} 段".format(len(sections)))

sec1_body = _extract_body(sections[0])
sec2_body = _extract_body(sections[1])
print("  段1: {}...".format(sec1_body[:40]))
print("  段2: {}...".format(sec2_body[:40]))
assert sec1_body, "段1不应为空"

t_a = _character_trigrams(sec1_body)
t_b = _character_trigrams(sec2_body)
sim3 = _jaccard(t_a, t_b)
print("  Jaccard: {:.2f} (应 > 0.3)".format(sim3))
assert sim3 >= 0.3, "感知理论段落应有些相似"

# ---- 3. 实际 MEMORY.md 去重 ----
print()
print("4. 当前 MEMORY.md 内容级去重：")
from memory_dedup import dedup_content
result = dedup_content(dry_run=True)
print("  段: {} → {}".format(result.get("sections_before", "?"), result.get("sections_after", "?")))
print("  对比 {} 对，发现 {} 对重复".format(result.get("pairs_checked", 0), result.get("duplicate_pairs", 0)))
print("  归档 {} 段".format(result.get("archived", 0)))

print()
print("=== ALL PASS ===")
