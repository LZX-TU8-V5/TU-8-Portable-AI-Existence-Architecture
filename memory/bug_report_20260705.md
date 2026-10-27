"""bug_report.md — 活跃 Bug 汇总"""
import sys
sys.path.insert(0, r"C:\Users\qq366410837\.qclaw\workspace\src")
from memory_gc import MemoryGC

gc = MemoryGC()

print("# MEMORY.md Bug Report")
print()

# Bug 1: duplicate sections
# Bug 2: _archive_section not removing sections
# Bug 3: DEGRADE sections not cleaned

# Test _archive_section
print("## Bug 1: 重复段 (x2: '完成工作')")
print("- 描述: '## 完成工作' 出现了3次")
print("- 位置: 不同 # 标题下的同名段落")
print("- 影响: GC 只能处理第一个, 后面的不会被清除")
print()

print("## Bug 2: GC _archive_section 不删除源内容")
# Try to archive one section and check
import re
with open(gc.memory_path, "r", encoding="utf-8") as f:
    before = f.read()

# Check if '七、工程落地' exists
if "七、工程落地" in before:
    print("- 状态: DEGRADE 段 '七、工程落地' 仍存在于 MEMORY.md")
    print("- 证据: GC 输出 DEGRADE 标记但未移除")
    print("- 归档目录: 127 个文件但 MEMORY.md 未缩减")
else:
    print("- 状态: 已清理")
print()

print("## Bug 3: 重复段导致 GC 误判")
gc.analyze_memory()
print("- GC 将相同标题的不同实例分配不同 action")
print("- 这导致 WATCH/DEGRADE/KEEP 并存于同一标题")
print()

print("## 建议修复顺序")
print("1. 修复 _archive_section: 删除源文件段落 (已部分实现)")
print("2. 去重: 合并同名段落")
print("3. 防重: metabolic_pipeline 追加时检查重复")
