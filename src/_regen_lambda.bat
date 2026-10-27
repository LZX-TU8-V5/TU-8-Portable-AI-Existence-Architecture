@echo off
"C:\Users\qq366410837\.workbuddy\binaries\python\versions\3.13.12\python.exe" -c "
import sys, os
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
os.chdir(r'C:\Users\qq366410837\.qclaw\workspace\src')
import json, pathlib
from datetime import datetime, timezone

# Load current surface_tension state for merging
st = json.loads(pathlib.Path(r'C:\Users\qq366410837\.qclaw\workspace\_agent_memory\surface_tension_state.json').read_text(encoding='utf-8'))
sv = st.get('spike_valley_vector', {})

# Compute P/D/F from current state
anxiety = sv.get('anxiety', 0.0)
anger = sv.get('anger', 0.0)
fear = sv.get('fear', 0.0)
joy = sv.get('joy', 0.0)
curiosity = sv.get('curiosity', 0.0)

# Load existing lambda_state to get pain info
ls_path = pathlib.Path(r'C:\Users\qq366410837\.qclaw\workspace\_agent_memory\lambda_state.json')
ls = json.loads(ls_path.read_text(encoding='utf-8')) if ls_path.exists() else {}

pain_int = ls.get('pain_int', 0.5)
pain_ext = ls.get('pain_ext', 1.0)
mode = ls.get('mode', 'stress')

F = max(anxiety, anger, fear) * 0.6 + pain_ext * 0.4
D = curiosity * 0.6 + 0.5 * 0.4  # basin_h approx 0.5
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

ls_path.write_text(json.dumps(new_ls, indent=2, ensure_ascii=False), encoding='utf-8')
print('lambda_state.json updated:')
print(json.dumps(new_ls, indent=2, ensure_ascii=False))
"
