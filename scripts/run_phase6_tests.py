"""Phase 6 集成测试运行器"""
import subprocess, sys, os

tests = [
    (r'C:\Users\qq366410837\.qclaw\workspace\scripts\test_phase66_anchor.py', 'Phase 6.6'),
    (r'C:\Users\qq366410837\.qclaw\workspace\tests\test_phase6_2_managers.py', 'Phase 6.2'),
    (r'C:\Users\qq366410837\.qclaw\workspace\tests\test_micro_sleep_integration_v2.py', 'MicroSleep'),
]

print('=== Phase 6 集成测试 ===')
all_ok = True
for path, name in tests:
    if not os.path.exists(path):
        print(f'SKIP: {name} ({os.path.basename(path)} not found)')
        continue
    r = subprocess.run([sys.executable, path], capture_output=True, text=True)
    lines = r.stdout.strip().split('\n')
    for l in lines:
        if any(k in l for k in ['结果', '汇总', '=== ']):
            print(f'{name}: {l.strip()}')
    ok = r.returncode == 0
    if not ok:
        print(f'{name}: FAILED (exit {r.returncode})')
        if r.stderr:
            print(f'  stderr: {r.stderr[:200]}')
        all_ok = False

print()
print('Phase 6 综合:', 'PASS' if all_ok else 'NEEDS REVIEW')
