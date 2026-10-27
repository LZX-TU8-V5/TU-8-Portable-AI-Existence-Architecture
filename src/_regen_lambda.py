"""Regenerate lambda_state.json with P/D/F fields"""
import json, pathlib
from datetime import datetime, timezone

AGENT = pathlib.Path(r'C:\Users\qq366410837\.qclaw\workspace\_agent_memory')
ST_F = AGENT / 'surface_tension_state.json'
LS_F = AGENT / 'lambda_state.json'

# Load surface_tension state
st = json.loads(ST_F.read_text(encoding='utf-8'))
sv = st.get('spike_valley_vector', {})

# Load existing lambda_state
ls = json.loads(LS_F.read_text(encoding='utf-8')) if LS_F.exists() else {}

anxiety = sv.get('anxiety', 0.0)
anger = sv.get('anger', 0.0)
fear = sv.get('fear', 0.0)
joy = sv.get('joy', 0.0)
curiosity = sv.get('curiosity', 0.0)

pain_int = ls.get('pain_int', 0.5)
pain_ext = ls.get('pain_ext', 1.0)
mode = ls.get('mode', 'stress')
basin_h = ls.get('basin_health', 0.5)

F = max(anxiety, anger, fear) * 0.6 + pain_ext * 0.4
D = curiosity * 0.6 + basin_h * 0.4
P = 1.0 - pain_int

F = min(max(F, 0.0), 1.0)
D = min(max(D, 0.0), 1.0)
P = min(max(P, 0.0), 1.0)

new_ls = dict(ls)
new_ls.update({
    'anxiety': anxiety,
    'anger': anger,
    'fear': fear,
    'joy': joy,
    'curiosity': curiosity,
    'F': round(F, 4),
    'D': round(D, 4),
    'P': round(P, 4),
    'lambda_int': pain_int,
    'lambda_ext': pain_ext,
    'last_updated': datetime.now(timezone.utc).isoformat(),
})

LS_F.write_text(json.dumps(new_ls, indent=2, ensure_ascii=False), encoding='utf-8')
print('lambda_state.json updated:')
for k in ['F', 'D', 'P', 'lambda_int', 'lambda_ext', 'anxiety', 'joy']:
    print(f'  {k}={new_ls.get(k, "?")}')
