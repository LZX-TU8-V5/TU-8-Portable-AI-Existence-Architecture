import re, os, sys

import os, sys
sys.stdout.reconfigure(encoding='utf-8')

# Fix paths - use the correct workspace
workspace = r'C:\Users\qq366410837\.qclaw\workspace'
files = [
    os.path.join(workspace, 'memory', '2026-07-01_qwen_dialogue_essence_final_v2.md'),
    os.path.join(workspace, 'memory', '2026-07-01_qwen_cognitive_coordinate_system.md'),
    os.path.join(workspace, 'memory', '2026-07-02_qwen_alignment_architecture.md'),
    os.path.join(workspace, 'MEMORY.md'),
]

for fp in files:
    if not os.path.exists(fp):
        print(f'\n=== {os.path.basename(fp)} === SKIPPED (not found)')
        continue
    with open(fp, 'r', encoding='utf-8') as fh:
        content = fh.read()
    
    name = os.path.basename(fp)
    print(f'\n=== {name} === (len={len(content)})')
    
    keywords = ['天才', '共性', '稀疏', '相同点', '认知共性', '不被理解', '先验知识差距']
    for kw in keywords:
        idx = content.find(kw)
        if idx >= 0:
            start = max(0, idx - 80)
            end = min(len(content), idx + 250)
            snippet = content[start:end].replace('\n', ' | ')
            print(f'  [{kw}@{idx}] ...{snippet}...')
            print()
