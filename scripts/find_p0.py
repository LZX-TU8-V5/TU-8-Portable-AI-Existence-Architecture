import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

with open(r'C:\Users\qq366410837\.qclaw\workspace\TODO_MASTER.md', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if any(kw in line for kw in ['P0', '安全模式', '矛盾仲裁', '错误翻译']):
        print(f"{i+1}: {line}", end="")
