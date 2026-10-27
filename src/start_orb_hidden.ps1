# 隐藏窗口启动 TU-8 Health Orb
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "C:\Users\qq366410837\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"
$psi.Arguments = "C:\Users\qq366410837\.qclaw\workspace\src\tu8_health_orb_ring.py"
$psi.WorkingDirectory = "C:\Users\qq366410837\.qclaw\workspace\src"
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$psi.CreateNoWindow = $true
[System.Diagnostics.Process]::Start($psi)
