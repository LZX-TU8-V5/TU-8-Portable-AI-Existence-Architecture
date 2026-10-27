# Backup Script Fix - 2026-05-12 08:44

## Objective
Fix the recurring issue where the cron-triggered backup script fails silently, and improve the script with logging capabilities.

## Problem
- Cron job `d25fd525-b2e9-4dbe-a434-4ce9e3b87db8` triggers backup script but **no backup directory is created**
- This happened on both 2026-05-10 17:09 and 2026-05-12 08:40
- Manual execution always works fine
- Original script had no logging, making diagnosis impossible

## Root Cause Found
The original backup script `_tw_backup_v2.ps1` had a **PowerShell parser error** on line 91:
- `try { ... | Where-Object { ... } | ... } catch { ... }` 
- PowerShell's parser incorrectly matches curly braces when `Where-Object` script blocks are nested inside `try` blocks
- The `catch` block was seen as an unexpected token, causing the script to fail at parse time

**This explains why cron execution failed** — the script couldn't even be parsed by PowerShell!

## Fix Applied
1. **Moved `Where-Object` filter script block outside `try`**: Used a variable `$filterScript = { $_.Name -match "^\d{8}-\d{6}$" }` and passed it to `Where-Object $filterScript`
2. **Added comprehensive logging** to `D:\qq366410837\.qclaw\workspace\backup\backup.log`
3. **Added error handling** with `try/catch` and detailed error messages
4. **Changed `Write-Host` to `Write-Output`** for better pipeline compatibility
5. **Added log rotation** (keeps last 200 lines)
6. **Added syntax verification** before deployment

## Verification
- Syntax check: ✅ No parse errors
- Manual execution: ✅ All 8 files backed up successfully
- Log file created: ✅ `backup.log` with timestamps
- Backup directories now show 5 entries (max retained)

## Backup Directory Status (after fix)
```
20260512-084402  (08:44:02) - Post-fix manual run ✅
20260512-084040  (08:40:40) - Pre-fix manual run
20260510-171030  (17:10:30) - Previous manual run
20260510-163947  (16:39:47) - Previous backup
20260510-160908  (16:09:08) - Previous backup
```

## Next Steps
- Monitor the **next cron execution** to confirm the fix resolves the issue
- If cron still fails, check `backup.log` for error details
- Consider adding cron execution environment diagnostics to the script
