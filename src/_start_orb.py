import subprocess, sys, pathlib, time, os
WS = r"C:\Users\qq366410837\.qclaw\workspace"
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"

# Kill existing orb processes
for proc in subprocess.run(["powershell", "-Command",
    "Get-Process python* | Where-Object {$_.CommandLine -like '*tu8_health_orb*'} | "
    "Select-Object Id | ConvertTo-Json"],
    capture_output=True, text=True, env=env).stdout.strip().splitlines():
    try:
        pid = json.loads(proc).get("Id") if proc.strip() else None
        if pid: os.kill(pid, 9)
    except: pass

time.sleep(1)
orb = pathlib.Path(WS) / "src" / "tu8_health_orb_ring.py"
p = subprocess.Popen([sys.executable, str(orb)],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    cwd=WS, env=env)
time.sleep(4)
alive = p.poll() is None
out, err = p.communicate() if not alive else (b"", b"")
print(f"PID={p.pid} alive={alive}")
if out: print("stdout:", out.decode("utf-8", errors="replace")[:200])
if err: print("stderr:", err.decode("utf-8", errors="replace")[:200])
