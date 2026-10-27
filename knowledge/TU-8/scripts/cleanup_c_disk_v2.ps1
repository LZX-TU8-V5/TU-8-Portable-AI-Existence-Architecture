# C盘清理脚本 - 极简稳定版
param($LogDir = "D:\qq366410837\.qclaw\logs")
$Timestamp = Get-Date -Format "yyyy-MM-dd"
$LogFile = Join-Path $LogDir "cleanup_$Timestamp.log"
$MarkerFile = Join-Path $LogDir "cleanup_marker_$Timestamp.txt"

# 检查是否已执行
if (Test-Path $MarkerFile) {
    Write-Host "今日已执行，退出"
    exit 0
}

# 创建日志目录
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

# 日志函数
function Write-Log {
    param($Message)
    $Entry = "2026-06-04 10:12:01 $Message"
    Add-Content -Path $LogFile -Value $Entry
    Write-Host $Entry
}

Write-Log "========== 清理开始 =========="

# 1. 清理 .deleted. 文件
$SessionDir = "$env:USERPROFILE\.qclaw\agents\main\sessions"
$DelFiles = Get-ChildItem -Path $SessionDir -Filter "*.deleted.*" -ErrorAction SilentlyContinue
$DelCount = $DelFiles.Count
if ($DelCount -gt 0) {
    $DelFiles | Remove-Item -Force
    Write-Log "已删除 .deleted. 文件: $DelCount 个"
}

# 2. 清理旧 checkpoint
$OldCheck = Get-ChildItem -Path $SessionDir -Filter "*.checkpoint.*" -ErrorAction SilentlyContinue | Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-7) }
$OldCount = $OldCheck.Count
if ($OldCount -gt 0) {
    $OldCheck | Remove-Item -Force
    Write-Log "已删除旧 checkpoint: $OldCount 个"
}

# 3. 清理 TEMP
$TempFiles = Get-ChildItem -Path $env:TEMP -File -ErrorAction SilentlyContinue | Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-7) }
$TempCount = $TempFiles.Count
if ($TempCount -gt 0) {
    $TempFiles | Remove-Item -Force
    Write-Log "已清理 TEMP 文件: $TempCount 个"
}

# 4. 写入标记
$MarkerContent = "执行时间: 2026-06-04 10:12:01$TempCount 个 TEMP 文件已清理"
Set-Content -Path $MarkerFile -Value $MarkerContent

Write-Log "========== 清理完成 =========="
exit 0
