# write_boot_time.ps1 — 开机时间写入脚本
# 挂 Windows 任务计划程序 → 每次开机自动运行
# 输出：C:\Users\qq366410837\.qclaw\workspace\_agent_memory\boot_timestamp.json
$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ss.fffzzz'
$unix  = [int64](Get-Date).ToUniversalTime().Subtract((Get-Date "1970-01-01")).TotalSeconds
$file  = "$env:USERPROFILE\.qclaw\workspace\_agent_memory\boot_timestamp.json"
@{
    boot_time   = $stamp
    boot_unix   = $unix
    host        = $env:COMPUTERNAME
    written_at  = $stamp
} | ConvertTo-Json | Out-File -FilePath $file -Encoding UTF8
Write-Host "boot_timestamp written: $stamp"
