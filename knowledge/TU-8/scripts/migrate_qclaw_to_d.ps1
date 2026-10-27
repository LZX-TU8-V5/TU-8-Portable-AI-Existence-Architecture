# ============================================================
# .qclaw 迁移脚本 - C盘迁移到D盘
# ============================================================
param([switch]$DryRun)

$ErrorActionPreference = "Continue"
$Source = "C:\Users\qq366410837\.qclaw"
$Target = "D:\qq366410837\.qclaw"
$ConfigFile = "$Source\openclaw.json"

Write-Host "============================================"
Write-Host "  .qclaw Migration (C: -> D:)"
Write-Host "============================================"

# 安全检查
if (-not (Test-Path $Source)) {
    Write-Host "[FAIL] Source not found: $Source"
    exit 1
}
if (-not (Test-Path $ConfigFile)) {
    Write-Host "[FAIL] Config not found: $ConfigFile"
    exit 1
}

# 统计
$totalSize = (Get-ChildItem $Source -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
Write-Host "[INFO] Total size: $([math]::Round($totalSize, 2)) GB"

# 备份配置
Write-Host "[STEP] Backing up config..."
$BackupFile = "$ConfigFile.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item $ConfigFile $BackupFile -Force

if (-not $DryRun) {
    Write-Host "[STEP] Copying files to D:"
    Copy-Item -Path "$Source\*" -Destination $Target -Recurse -Force -Exclude "*.tmp" -ProgressAction Continue
} else {
    Write-Host "[DRYRUN] Skipping actual copy"
}

# 修改配置
Write-Host "[STEP] Updating config paths..."
$configContent = Get-Content $ConfigFile -Raw

$oldSkillsPath = "C:\\Users\\qq366410837\\.qclaw\\skills"
$newSkillsPath = "D:\\qq366410837\\.qclaw\\skills"
$configContent = $configContent -replace [regex]::Escape($oldSkillsPath), $newSkillsPath

$oldDbPath = "C:\\Users\\qq366410837\\.qclaw\\memory\\lossless\\lcm.db"
$newDbPath = "D:\\qq366410837\\.qclaw\\memory\\lossless\\lcm.db"
$configContent = $configContent -replace [regex]::Escape($oldDbPath), $newDbPath

if (-not $DryRun) {
    Copy-Item $ConfigFile "$ConfigFile.before_migrate" -Force
    $configContent | Set-Content -Path $ConfigFile -Encoding UTF8
    Write-Host "[OK] Config updated"
} else {
    Write-Host "[DRYRUN] Would change: $oldSkillsPath -> $newSkillsPath"
    Write-Host "[DRYRUN] Would change: $oldDbPath -> $newDbPath"
}

# 验证
Write-Host "[STEP] Verifying..."
$sourceFiles = (Get-ChildItem $Source -Recurse -File -ErrorAction SilentlyContinue).Count
$targetFiles = (Get-ChildItem $Target -Recurse -File -ErrorAction SilentlyContinue).Count
Write-Host "Source files: $sourceFiles"
Write-Host "Target files: $targetFiles"

# 验证关键文件
$keyFiles = @(
    "D:\qq366410837\.qclaw\memory\lossless\lcm.db",
    "D:\qq366410837\.qclaw\openclaw.json"
)
foreach ($f in $keyFiles) {
    if (Test-Path $f) { Write-Host "[OK] $f" }
    else { Write-Host "[FAIL] $f NOT FOUND" }
}

Write-Host ""
Write-Host "============================================"
Write-Host "  Migration Script Complete"
Write-Host "============================================"
Write-Host "Next: Restart QClaw to apply changes"