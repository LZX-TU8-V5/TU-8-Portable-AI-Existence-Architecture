"""P0-5: 添加 decay_tick 事件（让张力自动回归）"""
import pathlib

p = pathlib.Path(r'C:\Users\qq366410837\.qclaw\workspace\src\surface_tension.py')
content = p.read_text(encoding='utf-8', errors='replace')

old = '    "session_frozen":    {"fear": +0.8, "anxiety": +0.9, "anger": +0.2},\n}'
new = '''    "session_frozen":    {"fear": +0.8, "anxiety": +0.9, "anger": +0.2},
    # [P0-5] 自动衰减：定时器触发，让张力缓慢回归基线
    "decay_tick":        {"anxiety": -0.15, "anger": -0.15, "fear": -0.10, "sadness": -0.10, "curiosity": -0.05, "joy": -0.05, "love": -0.02},
}'''

if old not in content:
    print('ERROR: target not found')
    exit(1)

new_content = content.replace(old, new, 1)
p.write_text(new_content, encoding='utf-8', errors='replace')
print('P0-5 added: decay_tick event type (all emotions gently decrease)')
