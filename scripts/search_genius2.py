import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

workspace = r'C:\Users\qq366410837\.qclaw\workspace'

all_files = [os.path.join(workspace, 'MEMORY.md')]
memory_dir = os.path.join(workspace, 'memory')
for f in sorted(os.listdir(memory_dir)):
    if f.endswith('.md'):
        all_files.append(os.path.join(memory_dir, f))

for fp in all_files:
    if not os.path.exists(fp):
        continue
    try:
        with open(fp, 'r', encoding='utf-8') as fh:
            content = fh.read()
    except UnicodeDecodeError:
        try:
            with open(fp, 'r', encoding='gbk') as fh:
                content = fh.read()
        except:
            continue
    
    name = os.path.basename(fp)
    
    # Search for broader patterns
    patterns = [
        ('.{0,40}(天才|不被理解|认知差距|稀疏区域|最大公约数|认知共性|求共性|先验知识差距|LLM在简单|认知偏见).{0,100}', 'key'),
    ]
    
    hits = []
    for pat, tag in patterns:
        for m in re.finditer(pat, content, re.DOTALL):
            snippet = m.group(0).replace('\n', ' ').strip()
            hits.append((m.start(), tag, snippet))
    
    if hits:
        hits.sort()
        print(f'\n=== {name} ===')
        for pos, tag, snippet in hits:
            print(f'  ...{snippet[:250]}...')
            print()
