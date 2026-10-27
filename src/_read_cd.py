import pathlib
p = pathlib.Path(r'C:\Users\qq366410837\.qclaw\workspace\src\cron_daemon.py')
content = p.read_text(encoding='utf-8', errors='replace')
lines = content.split('\n')
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped and not stripped.startswith('#'):
        print(f'L{i+1}: {stripped[:110]}')
