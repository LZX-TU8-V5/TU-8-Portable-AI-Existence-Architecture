# C盘清理脚本 - 最终稳定版
# 版本 4.0

param($LogDir = "D:\qq366410837\.qclaw\logs")

$ErrorActionPreference = "Continue"
$Timestamp = Get-Date -Format "yyyy-MM-dd"
$LogFile = Join-Path $LogDir ("cleanup_" + $Timestamp + ".log")
$MarkerFile = Join-Path $LogDir ("cleanup_marker_" + $Timestamp + ".txt")

# 创建目录
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

# 日志
function Write-Log {
    param($m, $l = "INFO")
    $e = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " [$l] " + $m
    Add-Content -Path $LogFile -Value $e
    Write-Host $e
}

# 检查标记
if (Test-Path $MarkerFile) {
    Write-Log "今日已执行" "SKIP"
    exit 0
}

Write-Log "========== 开始 ==========" "START"

# 1. 清理 .deleted. 文件
$SD = "$env:USERPROFILE\.qclaw\agents\main\sessions"
$DF = Get-ChildItem -Path $SD -Filter "*.deleted.*" -ErrorAction SilentlyContinue
$DC = 0
if ($DF -ne $null) { $DC = $DF.Count }
if ($DC -gt 0) {
    $DF | Remove-Item -Force
    Write-Log ("删除 .deleted. 文件: " + $DC + " 个") "CLEAN"
}

# 2. 清理旧 checkpoint
$CF = Get-ChildItem -Path $SD -Filter "*.checkpoint.*" -ErrorAction SilentlyContinue
$OC = 0
if ($CF -ne $null) {
    $Cut = (Get-Date).AddDays(-7)
    $OCF = $CF | Where-Object { $_.CreationTime -lt $Cut }
    if ($OCF -ne $null) { $OC = $OCF.Count }
    if ($OC -gt 0) {
        $OCF | Remove-Item -Force
        Write-Log ("删除旧 checkpoint: " + $OC + " 个") "CLEAN"
    }
}

# 3. 清理 TEMP
$TF = Get-ChildItem -Path $env:TEMP -File -ErrorAction SilentlyContinue | Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-7) }
$TC = 0
if ($TF -ne $null) { $TC = $TF.Count }
if ($TC -gt 0) {
    $TF | Remove-Item -Force
    Write-Log ("清理 TEMP: " + $TC + " 个") "CLEAN"
}

# 4. 写入标记
$MC = "执行时间: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "
"
$MC += "删除 .deleted.: " + $DC + "
"
$MC += "删除 checkpoint: " + $OC + "
"
$MC += "清理 TEMP: " + $TC + "
"
Set-Content -Path $MarkerFile -Value $MC

Write-Log "========== 完成 ==========" "END"
exit 0
