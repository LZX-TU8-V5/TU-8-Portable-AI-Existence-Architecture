# OpenClaw Cron Issue - Investigation Summary - 2026-05-12 14:05

## Objective
Diagnose why OpenClaw's cron-triggered backup script fails to execute, despite manual execution working perfectly.

## Cron Execution History
| Time (Asia/Shanghai) | Cron Triggered | Script Executed | Backup Created |
|----------------------|----------------|-------------------|-----------------|
| 2026-05-10 17:09 | ✅ | ❌ | ❌ |
| 2026-05-12 08:40 | ✅ | ❌ | ❌ |
| 2026-05-12 09:00 | ✅ | ❌ | ❌ |
| 2026-05-12 14:00 | ✅ | ❌ | ❌ |
| 2026-05-12 14:09 | ✅ | ❌ | ❌ |

## Key Findings

### 1. Script Works Manually ✅
- PowerShell script executes successfully when run manually
- All 8 files backed up correctly
- Cleanup logic works (maintains 5 most recent backups)
- Logging works (backup.log records all operations)

### 2. Batch File Wrapper Works Manually ✅
- `_backup_wrapper.bat` successfully invokes PowerShell script
- Log shows: `WRAPPER_STARTED` → `SCRIPT_STARTED` → `SCRIPT_FINISHED` → `WRAPPER_FINISHED`
- Exit code: 0 (success)

### 3. Cron Execution Fails ❌
- OpenClaw cron triggers the job (notifications received)
- **No `SCRIPT_STARTED` in backup.log** → script never starts
- **No `WRAPPER_STARTED` in cron_wrapper.log** (when triggered by cron)
- No backup directory created
- No error messages captured

### 4. Root Cause Hypothesis
**OpenClaw's cron is not correctly executing the command.**

The cron notification format:
```
[cron:d25fd525-b2e9-4dbe-a434-4ce9e3b87db8 workspace-backup] 运行备份脚本：powershell -ExecutionPolicy Bypass -File "D:\qq366410837\.qclaw\workspace\_tw_backup_v2.ps1"
```

Possibilities:
1. **Command parsing issue** - OpenClaw may be including `运行备份脚本：` as part of the command
2. **Execution context issue** - Cron runs in different user/permission context
3. **Path/encoding issue** - PowerShell executable or script path not accessible
4. **OpenClaw cron bug** - The cron execution mechanism may have a bug

## Files Created
| File | Purpose | Status |
|------|---------|--------|
| `_tw_backup_v2.ps1` | Main backup script v3 | ✅ Works manually |
| `_backup_wrapper.bat` | Batch file wrapper | ✅ Works manually |
| `_cron_diagnostic.ps1` | Environment diagnostic | ✅ Works manually |
| `backup\backup.log` | Backup script log | ✅ Working |
| `backup\cron_wrapper.log` | Wrapper log | ✅ Working (manual only) |
| `backup\cron_diagnostic.log` | Diagnostic log | ✅ Working (manual only) |

## Attempted Solutions

### 1. Fixed PowerShell Parser Error ✅
- Original script had `try { ... Where-Object { ... } ... } catch { ... }`
- PowerShell parser incorrectly matched curly braces
- **Fixed**: Removed `try/catch` around `Where-Object`

### 2. Added Comprehensive Logging ✅
- Early logging (`SCRIPT_STARTED` at very beginning)
- All operations logged with timestamps
- Cleanup operations logged

### 3. Created Batch File Wrapper ✅
- Wraps PowerShell execution
- Captures all output and errors
- **Works manually, but cron doesn't invoke it**

### 4. Searched for OpenClaw Cron Configuration ❌
- Checked `C:\Users\qq366410837\.openclaw\` - no cron config found
- Checked Windows Task Scheduler - no OpenClaw tasks
- Checked `latest.log` - no cron execution logs
- **OpenClaw's cron configuration location remains unknown**

## Next Steps / Request for User

### Option A: Check OpenClaw Cron Configuration
Please check OpenClaw's cron configuration:
1. Open OpenClaw settings/configuration
2. Look for "cron", "scheduled tasks", or "workspace-backup" job
3. Verify the command is exactly:
   ```
   powershell -ExecutionPolicy Bypass -File "D:\qq366410837\.qclaw\workspace\_tw_backup_v2.ps1"
   ```
4. Try changing the command to:
   ```
   cmd.exe /c "D:\qq366410837\.qclaw\workspace\_backup_wrapper.bat"
   ```

### Option B: Check OpenClaw Logs
1. Look for OpenClaw's execution logs
2. Check if there are error messages when cron job runs
3. Verify OpenClaw can access PowerShell executable

### Option C: Manual Backup + Monitor
Since manual execution works, you can:
1. Manually run backup before important work
2. Wait for next cron execution (observe if it ever works)
3. Consider reporting this as a bug to OpenClaw developers

## Technical Details for Debugging

If you can access OpenClaw's internals, check:
- Does OpenClaw's cron run as the same user as the interactive session?
- Does OpenClaw's cron have access to the PowerShell executable?
- Is the command string being parsed correctly (is `运行备份脚本：` being included)?
- Are there any error messages when the cron job triggers?

## Conclusion
The backup script itself is correctly written and works perfectly in manual execution. The issue is specifically with **OpenClaw's cron execution environment or command parsing**. Without access to modify OpenClaw's cron configuration or view its execution logs, I cannot further diagnose the issue.
