# 临时脚本 - 步骤3：分析 session 文件
$SessionDir = "$env:USERPROFILE\.qclaw\agents\main\sessions"
$LogDir = "D:\qq366410837\.qclaw\logs"
$Timestamp = "2026-06-05"

$MainSessions = Get-ChildItem -Path $SessionDir -File -ErrorAction SilentlyContinue | 
    Where-Object { $_.Name -notmatch 'checkpoint|\.deleted\.|sessions\.json|\.lock' } |
    Sort-Object LastWriteTime -Descending

$MainSessionCount = $MainSessions.Count
Write-Host "Total sessions: $MainSessionCount"

$AnalyzeSessions = $MainSessions | Select-Object -Skip 5
$AnalyzeCount = $AnalyzeSessions.Count

if ($AnalyzeCount -gt 0) {
    $AnalyzeFile = "$LogDir\session_analyze_$Timestamp.csv"
    
    $CsvRows = @()
    $CsvRows += "SessionID,LastWriteTime,Size(MB),DaysIdle"
    
    foreach ($s in $AnalyzeSessions) {
        $sessionId = $s.Name.Replace('.jsonl', '')
        $lastWrite = $s.LastWriteTime.ToString('yyyy-MM-dd HH:mm')
        $size = [math]::Round($s.Length/1MB, 2)
        $daysIdle = [math]::Round((Get-Date - $s.LastWriteTime).TotalDays, 0)
        $row = "$sessionId,$lastWrite,$size,$daysIdle"
        $CsvRows += $row
    }
    
    $CsvRows | Set-Content -Path $AnalyzeFile -Encoding UTF8
    Write-Host "CSV created: $AnalyzeFile"
    Write-Host "Sessions to analyze: $AnalyzeCount"
} else {
    Write-Host "All sessions within keep range (5 most recent)"
}
