# C盘空间自动清理脚本 - 完整稳定版 v5.0
# 作者: TU-8
# 功能: 清理 .deleted./旧checkpoint/TEMP + 生成 session 分析清单

param(
    [string]$LogDir = "D:\qq366410837\.qclaw\logs",
    [int]$CheckpointKeepDays = 7,
    [int]$SessionKeepCount = 5
)

$ErrorActionPreference = "Continue"
$Timestamp = Get-Date -Format "yyyy-MM-dd"
$LogFile = Join-Path $LogDir "cleanup_$Timestamp.log"
$MarkerFile = Join-Path $LogDir "cleanup_marker_$Timestamp.txt"

# 创建日志目录
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# 日志函数
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Entry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [$Level] $Message"
    Add-Content -Path $LogFile -Value $Entry
    Write-Host $Entry
}

# ============================================================
# 步骤0: 检查是否已执行
# ============================================================
Write-Log "开始检查执行状态..."

if (Test-Path $MarkerFile) {
    Write-Log "今日清理已完成，跳过执行" "SKIP"
    Write-Host "✅ 今日 ($Timestamp) 已执行清理，退出"
    exit 0
}

Write-Log "========== C盘空间清理开始 ==========" "START"
Write-Log "执行日期: $Timestamp"

# ============================================================
# 步骤1: 清理 .deleted. 文件
# ============================================================
Write-Log "开始清理 .deleted. 文件..."

$SessionDir = "$env:USERPROFILE\.qclaw\agents\main\sessions"
$DeletedCount = 0
$DeletedSize = 0

$DeletedFiles = Get-ChildItem -Path $SessionDir -Filter "*.deleted.*" -ErrorAction SilentlyContinue
if ($DeletedFiles -ne $null) {
    $DeletedCount = $DeletedFiles.Count
    $DeletedSize = ($DeletedFiles | Measure-Object -Property Length -Sum).Sum / 1MB
    $DeletedFiles | Remove-Item -Force
    Write-Log "已删除 .deleted. 文件: $DeletedCount 个, 释放 $([math]::Round($DeletedSize, 2)) MB" "CLEAN"
} else {
    Write-Log "无 .deleted. 文件需要清理" "INFO"
}

# ============================================================
# 步骤2: 清理旧 checkpoint 文件
# ============================================================
Write-Log "开始清理旧 checkpoint 文件..."

$OldCheckpointCount = 0
$OldCheckpointSize = 0
$ActiveCheckpoints = 0

$CheckpointFiles = Get-ChildItem -Path $SessionDir -Filter "*.checkpoint.*" -ErrorAction SilentlyContinue
if ($CheckpointFiles -ne $null) {
    $CutoffDate = (Get-Date).AddDays(-$CheckpointKeepDays)
    $OldCheckpoints = $CheckpointFiles | Where-Object { $_.CreationTime -lt $CutoffDate }
    
    if ($OldCheckpoints -ne $null) {
        $OldCheckpointCount = $OldCheckpoints.Count
        $OldCheckpointSize = ($OldCheckpoints | Measure-Object -Property Length -Sum).Sum / 1MB
        $OldCheckpoints | Remove-Item -Force
        Write-Log "已删除 $CheckpointKeepDays 天前 checkpoint: $OldCheckpointCount 个, 释放 $([math]::Round($OldCheckpointSize, 2)) MB" "CLEAN"
    } else {
        Write-Log "无过期 checkpoint 需要清理" "INFO"
    }
    
    $ActiveCheckpoints = $CheckpointFiles.Count - $OldCheckpointCount
    Write-Log "保留活跃 checkpoint: $ActiveCheckpoints 个"
} else {
    Write-Log "无 checkpoint 文件" "INFO"
}

# ============================================================
# 步骤3: 分析 session 文件（生成 CSV 清单）
# ============================================================
Write-Log "开始分析 session 文件..."

$AnalyzeCount = 0
$AnalyzeSize = 0
$AnalyzeFile = $null

$MainSessions = Get-ChildItem -Path $SessionDir -File -ErrorAction SilentlyContinue | 
    Where-Object { $_.Name -notmatch 'checkpoint|\.deleted\.|sessions\.json|\.lock' }

if ($MainSessions -ne $null) {
    $MainSessionCount = $MainSessions.Count
    $MainSessionSize = ($MainSessions | Measure-Object -Property Length -Sum).Sum / 1MB
    Write-Log "主 session 文件总数: $MainSessionCount, 总大小: $([math]::Round($MainSessionSize, 2)) MB"
    
    # 按最后写入时间排序
    $SortedSessions = $MainSessions | Sort-Object LastWriteTime -Descending
    $AnalyzeSessions = $SortedSessions | Select-Object -Skip $SessionKeepCount
    $AnalyzeCount = $AnalyzeSessions.Count
    
    if ($AnalyzeCount -gt 0) {
        $AnalyzeSize = ($AnalyzeSessions | Measure-Object -Property Length -Sum).Sum / 1MB
        $AnalyzeFile = Join-Path $LogDir "session_analyze_$Timestamp.csv"
        
        # 生成 CSV 文件（简单方式，避免管道问题）
        $CsvLines = @()
        $CsvLines += "SessionID,LastWriteTime,Size(MB),DaysIdle"
        
        foreach ($sess in $AnalyzeSessions) {
            $sid = $sess.Name.Replace('.jsonl', '')
            $lwt = $sess.LastWriteTime.ToString('yyyy-MM-dd HH:mm')
            $size = [math]::Round($sess.Length / 1MB, 2)
            $days = [math]::Round((Get-Date - $sess.LastWriteTime).TotalDays, 0)
            $CsvLines += "$sid,$lwt,$size,$days"
        }
        
        $CsvLines | Set-Content -Path $AnalyzeFile -Encoding UTF8
        
        Write-Log "需 AI 分析的 session: $AnalyzeCount 个, $([math]::Round($AnalyzeSize, 2)) MB, 清单已保存" "ANALYZE"
        Write-Log "分析清单路径: $AnalyzeFile"
    } else {
        Write-Log "所有 session 文件均在保留范围内" "INFO"
    }
} else {
    Write-Log "无 session 文件" "INFO"
}

# ============================================================
# 步骤4: 清理 TEMP 目录
# ============================================================
Write-Log "开始清理 TEMP 目录..."

$TempCount = 0
$TempSize = 0

$TempFiles = Get-ChildItem -Path $env:TEMP -File -ErrorAction SilentlyContinue | 
    Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-7) }

if ($TempFiles -ne $null) {
    $TempCount = $TempFiles.Count
    $TempSize = ($TempFiles | Measure-Object -Property Length -Sum).Sum / 1MB
    $TempFiles | Remove-Item -Force
    Write-Log "已清理 TEMP 过期文件: $TempCount 个, 释放 $([math]::Round($TempSize, 2)) MB" "CLEAN"
} else {
    Write-Log "TEMP 目录无需清理" "INFO"
}

# ============================================================
# 步骤5: 写入执行标记
# ============================================================
Write-Log "写入执行标记..."

$TotalFreed = $DeletedSize + $OldCheckpointSize + $TempSize

$MarkerContent = "执行时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" + "`r`n"
$MarkerContent += "删除 .deleted.: $DeletedCount ($([math]::Round($DeletedSize, 2)) MB)" + "`r`n"
$MarkerContent += "删除 checkpoint: $OldCheckpointCount ($([math]::Round($OldCheckpointSize, 2)) MB)" + "`r`n"
$MarkerContent += "保留 checkpoint: $ActiveCheckpoints" + "`r`n"
$MarkerContent += "TEMP 清理: $TempCount ($([math]::Round($TempSize, 2)) MB)" + "`r`n"
$MarkerContent += "需 AI 分析: $AnalyzeCount ($([math]::Round($AnalyzeSize, 2)) MB)" + "`r`n"

Set-Content -Path $MarkerFile -Value $MarkerContent -Encoding UTF8

# ============================================================
# 步骤6: 汇总报告
# ============================================================
Write-Log "========== 清理完成 ==========" "END"
Write-Log "总释放空间: $([math]::Round($TotalFreed, 2)) MB"
Write-Log "今日标记已创建: $MarkerFile"

# 输出统计信息（供 AI 读取）
Write-Log "========== 统计信息 ==========" "STATS"
Write-Log "DeletedCount=$DeletedCount"
Write-Log "DeletedSize=$([math]::Round($DeletedSize, 2))"
Write-Log "OldCheckpointCount=$OldCheckpointCount"
Write-Log "OldCheckpointSize=$([math]::Round($OldCheckpointSize, 2))"
Write-Log "TempCount=$TempCount"
Write-Log "TempSize=$([math]::Round($TempSize, 2))"
Write-Log "AnalyzeCount=$AnalyzeCount"
Write-Log "AnalyzeSize=$([math]::Round($AnalyzeSize, 2))"
if ($AnalyzeFile -ne $null) {
    Write-Log "AnalyzeFile=$AnalyzeFile"
}
Write-Log "TotalFreed=$([math]::Round($TotalFreed, 2))"

Write-Log "脚本执行完成"
exit 0
