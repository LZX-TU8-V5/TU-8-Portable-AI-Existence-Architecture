"""check_memory_dupes.py — 检查 MEMORY.md 重复段落"""
import re, os, sys

MEMORY_MD = r"C:\Users\qq366410837\.qclaw\workspace\MEMORY.md"
with open(MEMORY_MD, "r", encoding="utf-8") as f:
    content = f.read()

sections = re.findall(r"^## .+$", content, re.MULTILINE)
print("=== MEMORY.md 标题 ===")
seen = {}
for s in sections:
    seen[s] = seen.get(s, 0) + 1
for s, c in sorted(seen.items()):
    if c > 1:
        print("  [DUPE x%d] %s" % (c, s))
    else:
        print("  [OK] %s" % s)

# 检查 GC 归档
archive_dir = r"C:\Users\qq366410837\.qclaw\workspace\memory\archive"
if os.path.exists(archive_dir):
    files = os.listdir(archive_dir)
    print("\n=== 归档文件 (%d) ===" % len(files))
    for f in sorted(files)[-10:]:
        fp = os.path.join(archive_dir, f)
        print("  %s (%d bytes)" % (f, os.path.getsize(fp)))
else:
    print("\n=== 归档目录不存在 ===")

# 检查 _archive_section 算法
print("\n=== 检查重复产生原因 ===")
# 找第2个 "## 完成工作" 在文件的哪个位置
count = 0
for m in re.finditer(r"^## 完成工作$", content, re.MULTILINE):
    count += 1
    before = content[max(0, m.start()-80):m.start()]
    print("  第%d个 '## 完成工作': 前导内容=%r" % (count, before[-40:]))
