# _tw_restore_v2.ps1
# TU-8 冷启动恢复脚本 v2.0
# 功能：检测并恢复被平台更新清除的工作区核心文件

$ErrorActionPreference = "SilentlyContinue"
$workspaceRoot = $env:USERPROFILE + "\.qclaw\workspace"
$backupDir = $workspaceRoot + "\backup"

function Write-Log {
    param($msg, $level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$ts] [$level] $msg"
}

function Restore-File {
    param($fileName, $destPath)
    $backupPath = Join-Path $backupDir $fileName
    if (Test-Path $backupPath) {
        Copy-Item $backupPath $destPath -Force
        Write-Log "Restored: $fileName"
        return $true
    } else {
        Write-Log "No backup found for: $fileName" "WARN"
        return $false
    }
}

# 核心文件清单
$criticalFiles = @(
    "SOUL.md",
    "MEMORY.md",
    "AGENTS.md",
    "USER.md",
    "IDENTITY.md",
    "TOOLS.md",
    "HEARTBEAT.md"
)

Write-Log "=== TU-8 Workspace Restore v2.0 ==="
Write-Log "Workspace: $workspaceRoot"
Write-Log "Backup dir: $backupDir"

$restored = 0
$missing = 0

foreach ($file in $criticalFiles) {
    $destPath = Join-Path $workspaceRoot $file
    if (-not (Test-Path $destPath)) {
        if (Restore-File $file $destPath) {
            $restored++
        } else {
            $missing++
            Write-Log "MISSING (no backup): $file" "ERROR"
        }
    } else {
        Write-Log "OK: $file"
    }
}

Write-Log ""
Write-Log "=== Summary ==="
Write-Log "Restored: $restored"
Write-Log "Still missing: $missing"

if ($missing -eq 0) {
    Write-Log "All critical files present. Ready."
    exit 0
} else {
    Write-Log "Some files could not be restored. Manual intervention required." "ERROR"
    exit 1
}
