"""P0-5: 在 cron_daemon SCRIPTS 加 surface_tension_decay"""
import pathlib

p = pathlib.Path(r'C:\Users\qq366410837\.qclaw\workspace\src\cron_daemon.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Find surface_tension entry and add decay entry after it
old = '''        "surface_tension": {
            "script": "surface_tension.py",
            "args": ["--record", "session_frozen", "--magnitude", "0.3", "--source", "cron_loop"],
            "interval": 360,  # 6分钟
            "last_run": 0,
        },'''

new = '''        "surface_tension": {
            "script": "surface_tension.py",
            "args": ["--record", "session_frozen", "--magnitude", "0.3", "--source", "cron_loop"],
            "interval": 360,  # 6分钟
            "last_run": 0,
        },
        # [P0-5] 张力自动回归：每5分钟缓慢衰减
        "surface_tension_decay": {
            "script": "surface_tension.py",
            "args": ["--record", "decay_tick", "--magnitude", "1.0", "--source", "decay_loop"],
            "interval": 300,  # 5分钟
            "last_run": 0,
        },'''

if old not in content:
    print('ERROR: surface_tension entry not found')
    exit(1)

new_content = content.replace(old, new, 1)
p.write_text(new_content, encoding='utf-8', errors='replace')
print('P0-5 added: surface_tension_decay in cron_daemon (5min interval)')
