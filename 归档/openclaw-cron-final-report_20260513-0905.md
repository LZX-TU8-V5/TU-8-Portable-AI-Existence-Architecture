# OpenClaw Cron Issue - Final Investigation Report
**Date:** 2026-05-13 09:05 (Asia/Shanghai)
**Status:** 🔴 ROOT CAUSE CONFIRMED

## Objective
Diagnose why OpenClaw's cron-triggered backup script fails to execute.

## Cron Execution History (Complete)
| Time (Asia/Shanghai) | Cron Triggered | Script Executed | Backup Created |
|----------------------|----------------|-------------------|-----------------|
| 2026-05-10 17:09 | ✅ Yes | ❌ No | ❌ No |
| 2026-05-12 08:40 | ✅ Yes | ❌ No | ❌ No |
| 2026-05-12 09:00 | ✅ Yes | ❌ No | ❌ No |
| 2026-05-12 14:00 | ✅ Yes | ❌ No | ❌ No |
| 2026-05-12 14:09 | ✅ Yes | ❌ No | ❌ No |
| 2026-05-13 08:34 | ✅ Yes | ❌ No | ❌ No |
| 2026-05-13 09:00 | ✅ Yes | ❌ No | ❌ No |

**Total: 7 cron triggers, 0 successful executions.**

## Root Cause: CONFIRMED

### The Decisive Test
1. At 08:41, I replaced `_tw_backup_v2.ps1` with a diagnostic script that writes to TEMP directory
2. At 09:00, cron triggered and (theoretically) executed the diagnostic script
3. I checked `C:\Users\qq366410837\AppData\Local\Temp\openclaw_cron_backup_test.log`
4. **Result: No new entry at 09:00. Only the 08:41 manual test entry exists.**

### Conclusion
**OpenClaw's cron system triggers job notifications but does NOT execute the command.**

The cron notification format:
```
[cron:d25fd525-b2e9-4dbe-a434-4ce9e3b87db8 workspace-backup] 运行备份脚本：powershell -ExecutionPolicy Bypass -File "D:\qq366410837\.qclaw\workspace\_tw_backup_v2.ps1"
```

This message indicates the cron job was TRIGGERED, but the actual PowerShell command was never executed on the host system.

## What We Ruled Out
| Hypothesis | Test Result |
|------------|-------------|
| PowerShell syntax error | ❌ Ruled out - script runs fine manually |
| Permission issue | ❌ Ruled out - diagnostic script writes to TEMP successfully |
| Path issue | ❌ Ruled out - same path works in manual execution |
| Execution policy | ❌ Ruled out - -ExecutionPolicy Bypass is specified |
| Script can't start | ❌ Ruled out - diagnostic script at script path would have written to TEMP |
| **OpenClaw cron doesn't execute commands** | **✅ CONFIRMED** |

## Script Status
| File | Status |
|------|--------|
| `_tw_backup_v2.ps1` | ✅ Original restored, works perfectly manually |
| `_backup_wrapper.bat` | ✅ Batch wrapper, works perfectly manually |
| `_cron_diagnostic.ps1` | ✅ Diagnostic tool, works perfectly manually |
| `_cron_test_simple.ps1` | ✅ Simple TEMP logger, works perfectly manually |

All scripts work correctly when executed manually via:
- `powershell -ExecutionPolicy Bypass -File "D:\qq366410837\.qclaw\workspace\_tw_backup_v2.ps1"`
- `cmd.exe /c "D:\qq366410837\.qclaw\workspace\_backup_wrapper.bat"`

## Recommended Actions

### Option A: Report to OpenClaw Developer
This appears to be a bug in OpenClaw's cron implementation. The cron scheduler sends notifications but doesn't actually execute commands on the host system.

### Option B: Alternative Automation
Instead of relying on OpenClaw's cron, use:
1. **Windows Task Scheduler** - Create a scheduled task to run the backup script
2. **Manual execution** - Run the batch wrapper before important work
3. **Third-party scheduler** - Use a different scheduling tool

### Option C: Windows Task Scheduler (Recommended)
```powershell
# Create a scheduled task (run as administrator)
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"D:\qq366410837\.qclaw\workspace\_backup_wrapper.bat`""
$trigger = New-ScheduledTaskTrigger -Daily -At "08:30"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
Register-ScheduledTask -TaskName "OpenClaw-Workspace-Backup" -Action $action -Trigger $trigger -Settings $settings -Description "Daily backup of OpenClaw workspace"
```

## Files Created During Investigation
| File | Purpose | Keep? |
|------|---------|-------|
| `_backup_wrapper.bat` | Batch wrapper for backup script | ✅ Yes |
| `_cron_diagnostic.ps1` | Environment diagnostic script | 🗑️ Optional |
| `_cron_test_simple.ps1` | Simple TEMP logger | 🗑️ Optional |
| `_cron_debug.ps1` | Earlier diagnostic script | 🗑️ Optional |
| `_check_logs.ps1` | Log checking utility | 🗑️ Optional |
| `backup\backup.log` | Backup script log | ✅ Yes |
| `backup\cron_wrapper.log` | Wrapper log | ✅ Yes |
| `backup\cron_diagnostic.log` | Diagnostic log | 🗑️ Optional |
