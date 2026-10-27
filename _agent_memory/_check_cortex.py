import os

src = r'C:\Users\qq366410837\.qclaw\workspace\src'
for fname in sorted(os.listdir(src)):
    if 'cortex' in fname.lower():
        p = os.path.join(src, fname)
        sz = os.path.getsize(p)
        with open(p, 'r', encoding='utf-8', errors='replace') as fh:
            content = fh.read()
        print(fname, sz)
        print('  llm_related:', 'llm_related_keywords' in content)
        print('  degraded:', 'upstream_llm_degraded' in content)
        print('  v1.2:', 'v1.2' in content)
