# C盘空间自动清理脚本 - TU-8 巡航任务
# 每日执行1次，基于时间戳校验
# 版本: 2.4 (修复版)

param(
    [string]$LogDir = "D:\qq366410837\.qclaw\logs",
    [int]$CheckpointKeepDays = 7,
    [int]$SessionKeepCount = 5
)

$ErrorActionPreference = "Continue"
$Timestamp = Get-Date -Format "yyyy-MM-dd"
$LogFile = Join-Path $LogDir "cleanup_$Timestamp.log"
$MarkerFile = Join-Path $LogDir "cleanup_marker_$Timestamp.txt"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Entry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [$Level] $Message"
    Add-Content -Path $LogFile -Value $Entry
    Write-Host $Entry
}

if (Test-Path $MarkerFile) {
    Write-Log "Skip: already executed today" "SKIP"
    exit 0
}

Write-Log "========== C盘空间清理开始 ==========" "START"
Write-Log "Date: $Timestamp"

# === 1. 清理 .deleted. 文件 ===
$SessionDir = "$env:USERPROFILE\.qclaw\agents\main\sessions"
$DeletedCount = 0
$DeletedSize = 0.0

$DeletedFiles = @(Get-ChildItem -Path $SessionDir -Filter "*.deleted.*" -ErrorAction SilentlyContinue)
if ($DeletedFiles.Count -gt 0) {
    $DeletedCount = $DeletedFiles.Count
    $DeletedSize = [math]::Round(($DeletedFiles | Measure-Object -Property Length -Sum).Sum / 1MB, 2)
    $DeletedFiles | Remove-Item -Force
    Write-Log "CLEAN .deleted. files: $DeletedCount files, freed $DeletedSize MB" "CLEAN"
} else {
    Write-Log "No .deleted. files to clean" "INFO"
}

# === 2. 清理超过 N 天的 checkpoint 文件 ===
$OldCheckpointCount = 0
$OldCheckpointSize = 0.0

$CheckpointFiles = @(Get-ChildItem -Path $SessionDir -Filter "*.checkpoint.*" -ErrorAction SilentlyContinue)
$OldCheckpoints = @($CheckpointFiles | Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-$CheckpointKeepDays) })

if ($OldCheckpoints.Count -gt 0) {
    $OldCheckpointCount = $OldCheckpoints.Count
    $OldCheckpointSize = [math]::Round(($OldCheckpoints | Measure-Object -Property Length -Sum).Sum / 1MB, 2)
    $OldCheckpoints | Remove-Item -Force
    Write-Log "CLEAN old checkpoints: $OldCheckpointCount files, freed $OldCheckpointSize MB" "CLEAN"
} else {
    Write-Log "No expired checkpoints to clean" "INFO"
}

$ActiveCheckpoints = $CheckpointFiles.Count - $OldCheckpointCount
Write-Log "Active checkpoints retained: $ActiveCheckpoints"

# === 3. 主 session 文件分析 ===
$AnalyzeCount = 0
$AnalyzeSize = 0.0
$AnalyzeFile = ""

$MainSessions = @(Get-ChildItem -Path $SessionDir -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notmatch 'checkpoint|\.deleted\.|sessions\.json|\.lock' } |
    Sort-Object LastWriteTime -Descending)

$MainSessionCount = $MainSessions.Count
if ($MainSessionCount -gt 0) {
    $MainSessionSize = [math]::Round(($MainSessions | Measure-Object -Property Length -Sum).Sum / 1MB, 2)
} else {
    $MainSessionSize = 0.0
}
Write-Log "Main session files: $MainSessionCount total, $MainSessionSize MB"

$AnalyzeSessions = @($MainSessions | Select-Object -Skip $SessionKeepCount)
$AnalyzeCount = $AnalyzeSessions.Count

if ($AnalyzeCount -gt 0) {
    $AnalyzeSize = [math]::Round(($AnalyzeSessions | Measure-Object -Property Length -Sum).Sum / 1MB, 2)
    $AnalyzeFile = Join-Path $LogDir "session_analyze_$Timestamp.csv"

    $CsvRows = @()
    $CsvRows += "SessionID,LastWriteTime,SizeMB,DaysIdle"
    foreach ($s in $AnalyzeSessions) {
        $sid = $s.Name.Replace('.jsonl','')
        $lwt = $s.LastWriteTime.ToString('yyyy-MM-dd HH:mm')
        $sz = [math]::Round($s.Length/1MB, 2)
        $ts = (Get-Date) - $s.LastWriteTime
        $idle = [math]::Round($ts.TotalDays, 0)
        $CsvRows += "$sid,$lwt,$sz,$idle"
    }

    $CsvRows | Set-Content -Path $AnalyzeFile -Encoding UTF8
    Write-Log "ANALYZE sessions: $AnalyzeCount files, $AnalyzeSize MB - list saved" "ANALYZE"
    Write-Log "Analyze file: $AnalyzeFile"
} else {
    Write-Log "All sessions within retention range" "INFO"
}

# === 4. 清理用户 TEMP 目录 ===
$TempCount = 0
$TempSize = 0.0

$TempFiles = @(Get-ChildItem -Path $env:TEMP -File -ErrorAction SilentlyContinue |
    Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-7) })

if ($TempFiles.Count -gt 0) {
    $TempCount = $TempFiles.Count
    $TempSize = [math]::Round(($TempFiles | Measure-Object -Property Length -Sum).Sum / 1MB, 2)
    $TempFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Log "CLEAN TEMP old files: $TempCount files, freed $TempSize MB" "CLEAN"
} else {
    Write-Log "TEMP no expired files" "INFO"
}

# === 5. 写入执行日期标记 ===
$TotalFreed = [math]::Round($DeletedSize + $OldCheckpointSize + $TempSize, 2)

$MarkerLines = @()
$MarkerLines += "ExecTime: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$MarkerLines += "DeletedFiles: $DeletedCount, ${DeletedSize}MB"
$MarkerLines += "OldCheckpoints: $OldCheckpointCount, ${OldCheckpointSize}MB"
$MarkerLines += "ActiveCheckpoints: $ActiveCheckpoints"
$MarkerLines += "TempFiles: $TempCount, ${TempSize}MB"
$MarkerLines += "SessionsToAnalyze: $AnalyzeCount, ${AnalyzeSize}MB"

$MarkerLines | Set-Content -Path $MarkerFile -Encoding UTF8

# === 6. 汇总报告 ===
Write-Log "========== Cleanup Complete ==========" "END"
Write-Log "Total freed: $TotalFreed MB"
Write-Log "Marker: $MarkerFile"

Write-Log "STATS:DeletedCount=$DeletedCount"
Write-Log "STATS:DeletedSize=$DeletedSize"
Write-Log "STATS:OldCheckpointCount=$OldCheckpointCount"
Write-Log "STATS:OldCheckpointSize=$OldCheckpointSize"
Write-Log "STATS:TempCount=$TempCount"
Write-Log "STATS:TempSize=$TempSize"
Write-Log "STATS:AnalyzeCount=$AnalyzeCount"
Write-Log "STATS:AnalyzeSize=$AnalyzeSize"
if ($AnalyzeFile -ne "") {
    Write-Log "STATS:AnalyzeFile=$AnalyzeFile"
}
Write-Log "STATS:TotalFreed=$TotalFreed"

exit 0
