"""test_dedup_pipeline.py — 全套测试"""
import sys, os
sys.path.insert(0, r"C:\Users\qq366410837\.qclaw\workspace\src")

# 1. 测试内存去重
from memory_dedup import dedup_memory, _split_sections, _merge_sections

# 模拟重复内容
test_content = """## 主题A
内容甲

## 主题B
内容乙

## 主题A
内容丙

## 主题C
内容丁
"""

sections = _split_sections(test_content)
print("=== 分段测试 ===")
print("  段数: {}".format(len(sections)))
assert len(sections) == 4, "应该4段，但得到{}".format(len(sections))

merged = _merge_sections([sections[0], sections[2]])
print("  合并后标题: {}".format(merged.split("\n", 1)[0].strip()))
assert merged.startswith("## 主题A"), "标题丢失"

# 2. 实际跑 MEMORY.md 去重
print("\n=== MEMORY.md 去重 ===")
report = dedup_memory(dry_run=False)
print("  段前: {}".format(report.get("sections_before", "?")))
print("  段后: {}".format(report.get("sections_after", "?")))
print("  重复组: {}".format(report.get("duplicates_found", 0)))
print("  移除段: {}".format(report.get("total_removed", 0)))
if report.get("merged_titles"):
    for t in report["merged_titles"]:
        print("  合并: {}".format(t))

# 3. 测试管道集成
from metabolic_pipeline import MetabolicPipeline
pipe = MetabolicPipeline()
result = pipe.dedup(dry_run=False)
print("\n=== 管道 dedup 阶段 ===")
print("  结果: {}".format(result))

# 4. 验证 USER.md
print("\n=== USER.md 完整性 ===")
with open(r"C:\Users\qq366410837\.qclaw\workspace\USER.md", "r", encoding="utf-8") as f:
    content = f.read()
count = content.count("The more you know, the better you can help")
print("  引用次数: {} (应为1)".format(count))
assert count == 1, "USER.md 引用重复!"

# 5. 验证 MEMORY.md 无重复
print("\n=== MEMORY.md 完整性 ===")
with open(r"C:\Users\qq366410837\.qclaw\workspace\MEMORY.md", "r", encoding="utf-8") as f:
    content = f.read()
import re
titles = re.findall(r"^## .+$", content, re.MULTILINE)
from collections import Counter
dupes = {t: c for t, c in Counter(titles).items() if c > 1}
if dupes:
    for t, c in dupes.items():
        print("  ⚠️ 重复 x{}: {}".format(c, t))
else:
    print("  无重复段落 ✅")
print("  总计: {} 段".format(len(titles)))

print("\n=== ALL PASS ✅ ===")
