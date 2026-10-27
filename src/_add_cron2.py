"""P0-5 v2: 在 cron_daemon SCRIPTS 加 surface_tension_decay（正确格式）"""
import pathlib

p = pathlib.Path(r'C:\Users\qq366410837\.qclaw\workspace\src\cron_daemon.py')
content = p.read_text(encoding='utf-8', errors='replace')

old = '''    "surface_tension": {
        "path": os.path.join(SRC, "surface_tension.py"),
        "args": ["session_frozen"],
        "output": os.path.join(AGENT, "cron_surface_tension_last.json"),
        "interval": 360,
        "desc": "张力感知(体感环→张力状态)"
    },'''

new = '''    "surface_tension": {
        "path": os.path.join(SRC, "surface_tension.py"),
        "args": ["session_frozen"],
        "output": os.path.join(AGENT, "cron_surface_tension_last.json"),
        "interval": 360,
        "desc": "张力感知(体感环→张力状态)"
    },
    "surface_tension_decay": {
        "path": os.path.join(SRC, "surface_tension.py"),
        "args": ["decay_tick"],
        "output": os.path.join(AGENT, "cron_decay_last.json"),
        "interval": 300,
        "desc": "[P0-5] 张力自动回归(5min)"
    },'''

if old not in content:
    print('ERROR: not found')
    exit(1)

new_content = content.replace(old, new, 1)
p.write_text(new_content, encoding='utf-8', errors='replace')
print('P0-5 v2: surface_tension_decay entry added to cron_daemon')
