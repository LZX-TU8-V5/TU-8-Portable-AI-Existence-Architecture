import os, json, glob

w = r'C:\Users\qq366410837\.qclaw\workspace'

# task timer log
log = os.path.join(w, 'scripts', 'task_timer_log.jsonl')
if os.path.exists(log):
    lines = [json.loads(l) for l in open(log, encoding='utf-8') if l.strip()]
    print(f'task_timer_log: {len(lines)} 条')
    if lines:
        for l in lines[-3:]:
            print(f"  [{l.get('type','?')}] {l.get('task','?')} status={l.get('status','?')}")

# pending events
pe = os.path.join(w, 'memory', 'pending_events.jsonl')
if os.path.exists(pe):
    lines = [json.loads(l) for l in open(pe, encoding='utf-8') if l.strip()]
    print(f'\npending_events: {len(lines)} 条')
    for l in lines[:3]:
        print(f"  [{l.get('type')}] {str(l)[:80]}")

# pending hypotheses
ph = os.path.join(w, 'memory', 'pending_hypotheses.jsonl')
if os.path.exists(ph):
    lines = [json.loads(l) for l in open(ph, encoding='utf-8') if l.strip()]
    print(f'\npending_hypotheses: {len(lines)} 条')

# silence timer
st = os.path.join(w, 'scripts', 'silence_timer.py')
if os.path.exists(st):
    size = os.path.getsize(st)
    print(f'\nsilence_timer.py: {size}b — 状态?')

# pending care
pc = os.path.join(w, 'scripts', 'pending_care.py')
if os.path.exists(pc):
    size = os.path.getsize(pc)
    print(f'pending_care.py: {size}b — 未接入')

# Check what task files reference each other
src_files = glob.glob(os.path.join(w, 'src', '*.py'))
print(f'\n=== src/*.py ({len(src_files)} 个) ===')
for f in sorted(src_files):
    fname = os.path.basename(f)
    print(f"  {fname}")
