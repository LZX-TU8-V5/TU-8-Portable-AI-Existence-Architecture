@echo off
"C:\Users\qq366410837\.workbuddy\binaries\python\versions\3.13.12\python.exe" -c "
import json, pathlib
f = pathlib.Path(r'C:\Users\qq366410837\.qclaw\workspace\_agent_memory\lambda_state.json')
print('lambda_state.json:')
if f.exists():
    d = json.loads(f.read_text(encoding='utf-8'))
    print(json.dumps(d, indent=2, ensure_ascii=False))
else:
    print('NOT FOUND')
print()
f2 = pathlib.Path(r'C:\Users\qq366410837\.qclaw\workspace\_agent_memory\surface_tension_state.json')
print('surface_tension_state.json keys:', list(json.loads(f2.read_text(encoding='utf-8')).keys()) if f2.exists() else 'NOT FOUND')
"
