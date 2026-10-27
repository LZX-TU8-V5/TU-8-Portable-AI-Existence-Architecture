import subprocess

# List all python processes
r = subprocess.run(["powershell", "-Command",
    "Get-Process python* | ForEach-Object { "
    "Write-Output ('PID:' + $_.Id + ' CMD:' + $_.CommandLine) }"],
    capture_output=True, text=True)
lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
print(f"Total python procs: {len(lines)}")
for l in lines:
    print(l)
