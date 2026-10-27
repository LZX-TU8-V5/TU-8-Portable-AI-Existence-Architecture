# restore_workspace.ps1
# 检查 C: workspace 关键文件，缺失则从 D: 恢复
$src = "C:\Users\qq366410837\.openclaw\workspace"
$primary = "D:\qq366410837\.qclaw\workspace"
$backupRoot = "D:\qq366410837\.qclaw\workspace\backup"

$critical = @("SOUL.md","AGENTS.md","MEMORY.md","USER.md","IDENTITY.md","TOOLS.md","HEARTBEAT.md")

$latestBackup = $null
if (Test-Path $backupRoot) {
    $dirs = Get-ChildItem $backupRoot -Directory
    if ($dirs) {
        $latestBackup = $dirs | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    }
}

if ($latestBackup) {
    Write-Host "[INFO] Latest backup: $($latestBackup.FullName)"
} else {
    Write-Host "[INFO] No timestamped backup, using primary storage"
}

$restored = 0
foreach ($file in $critical) {
    $srcFile = Join-Path $src $file
    if (-not (Test-Path $srcFile)) {
        $primaryFile = Join-Path $primary $file
        $srcOk = $false
        if (Test-Path $primaryFile) {
            Copy-Item $primaryFile $srcFile -Force
            Write-Host "[RESTORE] $file <- D:\primary"
            $restored++
            $srcOk = $true
        }
        if (-not $srcOk -and $latestBackup) {
            $backupFile = Join-Path $latestBackup.FullName $file
            if (Test-Path $backupFile) {
                Copy-Item $backupFile $srcFile -Force
                Write-Host "[RESTORE] $file <- backup"
                $restored++
            } else {
                Write-Host "[WARN] $file not found in primary or backup"
            }
        }
    } else {
        Write-Host "[OK]    $file exists"
    }
}

# 恢复 memory\ 目录
$memSrc = Join-Path $src "memory"
if (-not (Test-Path $memSrc)) {
    $memPrimary = Join-Path $primary "memory"
    if (Test-Path $memPrimary) {
        Copy-Item $memPrimary $memSrc -Recurse -Force
        Write-Host "[RESTORE] memory\ <- D:\primary"
        $restored++
    } elseif ($latestBackup) {
        $memBackup = Join-Path $latestBackup.FullName "memory"
        if (Test-Path $memBackup) {
            Copy-Item $memBackup $memSrc -Recurse -Force
            Write-Host "[RESTORE] memory\ <- backup"
            $restored++
        }
    }
}

Write-Host "[DONE] Restored $restored file(s)"
