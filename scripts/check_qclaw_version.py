import os, json
from datetime import datetime

exe_dir = r'D:\Program Files\QClaw\v0.2.29.592'
print('=== QClaw 目录文件 ===')
for f in os.listdir(exe_dir):
    fp = os.path.join(exe_dir, f)
    if os.path.isfile(fp):
        stat = os.stat(fp)
        mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()
        size_mb = stat.st_size // 1024 // 1024
        print(f'  {f}: {size_mb}MB, mtime={mtime}')

print()
pkg = r'D:\Program Files\QClaw\v0.2.29.592\resources\openclaw\node_modules\openclaw\package.json'
if os.path.exists(pkg):
    with open(pkg, encoding='utf-8') as f:
        p = json.load(f)
    print(f'openclaw package.json version: {p.get("version")}')
else:
    print('package.json not found')

print()
# Check if there's a newer version directory
try:
    dirs = [d for d in os.listdir(r'D:\Program Files\QClaw') if d.startswith('v')]
    print(f'Version directories: {sorted(dirs)}')
except Exception as e:
    print(f'Cannot list versions: {e}')
