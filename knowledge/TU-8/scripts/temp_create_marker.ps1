# 创建标记文件
$LogDir = "D:\qq366410837\.qclaw\logs"
$Timestamp = "2026-06-05"
$MarkerFile = "$LogDir\cleanup_marker_$Timestamp.txt"

$content = @()
$content += "ExecTime: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$content += "DeletedFiles: 0"
$content += "OldCheckpoints: cleaned"
$content += "TempFiles: cleaned"
$content += "SessionsToAnalyze: 3"

$content | Set-Content -Path $MarkerFile -Encoding UTF8
Write-Host "Marker file created: $MarkerFile"
