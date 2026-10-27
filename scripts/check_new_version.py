import os, json

print('=== v0.2.30.594 (new) ===')
new_pkg = r'D:\Program Files\QClaw\v0.2.30.594\resources\openclaw\node_modules\openclaw\package.json'
if os.path.exists(new_pkg):
    with open(new_pkg, encoding='utf-8') as f:
        p = json.load(f)
    print(f'openclaw version: {p.get("version")}')
    print(f'description: {p.get("description", "")[:80]}')
else:
    print('package.json not found in new version')
    # Try alternate path
    alt = r'D:\Program Files\QClaw\v0.2.30.594\resources\openclaw\package.json'
    if os.path.exists(alt):
        with open(alt, encoding='utf-8') as f:
            p = json.load(f)
        print(f'openclaw version (alt path): {p.get("version")}')
    else:
        print('No package.json found at alternate path either')

print()
print('=== v0.2.29.592 (old) ===')
old_pkg = r'D:\Program Files\QClaw\v0.2.29.592\resources\openclaw\node_modules\openclaw\package.json'
if os.path.exists(old_pkg):
    with open(old_pkg, encoding='utf-8') as f:
        p2 = json.load(f)
    print(f'openclaw version: {p2.get("version")}')
else:
    print('package.json not found in old version')

print()
print('=== File sizes comparison ===')
files_to_check = ['QClaw.exe', 'resources/openclaw/node_modules.zip']
for vdir in ['v0.2.29.592', 'v0.2.30.594']:
    base = rf'D:\Program Files\QClaw\{vdir}'
    for f in files_to_check:
        fp = os.path.join(base, f.replace('/', os.sep))
        if os.path.exists(fp):
            size_mb = os.stat(fp).st_size // 1024 // 1024
            mtime = os.stat(fp).st_mtime
            import datetime
            dt = datetime.datetime.fromtimestamp(mtime).isoformat()
            print(f'  {vdir}/{f}: {size_mb}MB, mtime={dt}')
        else:
            print(f'  {vdir}/{f}: NOT FOUND')
