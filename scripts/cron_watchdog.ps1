# cron_watchdog.ps1 - TU-8 cron daemon watchdog
# Checks if cron_daemon.py is running; starts it if missing.
# Called by Windows Task Scheduler TU8_CronWatchdog every 5 min.

$ErrorActionPreference = "Continue"

$WS = "C:\Users\qq366410837\.qclaw\workspace"
$PY = "C:\Users\qq366410837\.workbuddy\binaries\python\versions\3.13.12\python.exe"
$DAEMON = "$WS\src\cron_daemon.py"
$LOG = "$WS\_agent_memory\cron_watchdog.log"

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts [watchdog] $msg" | Add-Content -Path $LOG -Encoding UTF8
}

Write-Log "watchdog invoked"

try {
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction Stop
    $running = $procs | Where-Object { $_.CommandLine -like "*cron_daemon.py*" }
} catch {
    Write-Log "CIM query failed: $_"
    $running = $null
}

if ($running) {
    Write-Log "alive PID=$($running.ProcessId)"
    exit 0
}

Write-Log "NOT running - starting daemon"

try {
    $p = Start-Process -FilePath $PY -ArgumentList @($DAEMON, "--daemon", "--interval", "300") -WindowStyle Hidden -PassThru -RedirectStandardOutput "$WS\_agent_memory\cron_daemon_run.log" -RedirectStandardError "$WS\_agent_memory\cron_daemon_run.err" -ErrorAction Stop
    Start-Sleep -Seconds 2
    $check = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*cron_daemon.py*" }
    if ($check) {
        Write-Log "started OK PID=$($check.ProcessId)"
    } else {
        Write-Log "FAILED to start (no process found after 2s)"
    }
} catch {
    Write-Log "EXCEPTION: $_"
}
