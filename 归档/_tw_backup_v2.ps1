# backup_workspace.ps1 v3
# 同步 C: OpenClaw workspace 关键文件到 D: 备份
# 增加日志记录和错误处理，方便排查 cron 执行问题

$ErrorActionPreference = "Continue"

# 配置
$src = "C:\Users\qq366410837\.openclaw\workspace"
$dstRoot = "D:\qq366410837\.qclaw\workspace\backup"
$logFile = "D:\qq366410837\.qclaw\workspace\backup\backup.log"
$dateStr = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $dstRoot $dateStr

# 确保备份目录存在
if (-not (Test-Path $dstRoot)) {
    New-Item -ItemType Directory -Path $dstRoot -Force | Out-Null
}

# 日志函数：同时输出到控制台和日志文件
function Write-Log($Message) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Write-Output $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
}

# 记录脚本启动
Write-Log "========== SCRIPT_STARTED =========="
Write-Log "PowerShell version: $($PSVersionTable.PSVersion)"
Write-Log "Working directory: $(Get-Location)"
Write-Log "Source: $src"
Write-Log "Destination: $backupDir"

$critical = @("SOUL.md","AGENTS.md","MEMORY.md","USER.md","IDENTITY.md","TOOLS.md","HEARTBEAT.md")

# 创建本次备份目录
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}
Write-Log "Backup directory created: $backupDir"

$backed = 0
$failed = 0

foreach ($file in $critical) {
    $srcFile = Join-Path $src $file
    if (Test-Path $srcFile) {
        $dstFile = Join-Path $backupDir $file
        Copy-Item $srcFile $dstFile -Force -ErrorAction SilentlyContinue
        if (Test-Path $dstFile) {
            Write-Log "[OK] $file"
            $backed++
        } else {
            Write-Log "[ERROR] Failed to copy $file"
            $failed++
        }
    } else {
        Write-Log "[SKIP] $file (not found)"
    }
}

# 备份 memory\ 目录
$memSrc = Join-Path $src "memory"
if (Test-Path $memSrc) {
    $memDst = Join-Path $backupDir "memory"
    Copy-Item $memSrc $memDst -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path $memDst) {
        Write-Log "[OK] memory\"
        $backed++
    } else {
        Write-Log "[ERROR] Failed to copy memory\"
        $failed++
    }
} else {
    Write-Log "[SKIP] memory\ (not found)"
}

# 维护：保留最近5份备份
Write-Log "[CLEAN] Checking backup count..."
$allBackups = @(Get-ChildItem $dstRoot -Directory | Where-Object { $_.Name -match "^\d{8}-\d{6}$" } | Sort-Object Name -Descending)
Write-Log "[CLEAN] Found $($allBackups.Count) backups"
$idx = 0
foreach ($dir in $allBackups) {
    $idx++
    if ($idx -gt 5) {
        Write-Log "[CLEAN] Removing: $($dir.Name)"
        Remove-Item $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
        Write-Log "[CLEAN] Removed: $($dir.Name)"
    }
}

# 清理旧日志（只保留最后200行）
if (Test-Path $logFile) {
    $lines = @(Get-Content $logFile -Encoding UTF8 -ErrorAction SilentlyContinue)
    if ($lines.Count -gt 200) {
        $lines | Select-Object -Last 200 | Set-Content $logFile -Encoding UTF8
    }
}

$status = "SUCCESS"
if ($failed -gt 0) { $status = "COMPLETED_WITH_ERRORS" }
Write-Log "[DONE] $backed file(s) backed up, $failed error(s). Status: $status"
Write-Log "========== SCRIPT_FINISHED =========="

if ($failed -gt 0) { exit 1 }
