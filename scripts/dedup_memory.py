"""
dedup_memory.py — 临时 MEMORY.md 去重脚本
移除重复的 ## 段落（按标题去重，保留第一个出现的）
"""
import re, pathlib

MEMORY_MD = pathlib.Path(r'C:\Users\qq366410837\.qclaw\workspace\MEMORY.md')

content = MEMORY_MD.read_text(encoding='utf-8')
lines = content.splitlines(keepends=True)

seen_titles = set()
new_lines = []
removed = 0
current_section = []
in_section = False

for line in lines:
    if line.startswith('## '):
        # 上一个段落结束，写入
        if current_section:
            new_lines.extend(current_section)
            current_section = []
        
        title = line.strip()
        if title in seen_titles:
            removed += 1
            current_section = []  # 跳过此段
            in_section = False
            continue
        else:
            seen_titles.add(title)
            current_section = [line]
            in_section = True
    elif in_section:
        current_section.append(line)

# 最后一段
if current_section:
    new_lines.extend(current_section)

MEMORY_MD.write_text(''.join(new_lines), encoding='utf-8')
print('[OK] 去重完成')
print('  原段落数: %d' % len(re.findall(r'^## .+$', content, re.MULTILINE)))
print('  新段落数: %d' % len(re.findall(r'^## .+$', MEMORY_MD.read_text(encoding='utf-8'), re.MULTILINE)))
print('  移除重复: %d 段' % removed)
