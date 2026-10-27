' 隐藏窗口启动 TU-8 Health Orb
' 使用 pythonw.exe 避免黑窗口

Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """C:\Users\qq366410837\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"" """ & _
    WshShell.CurrentDirectory & "\tu8_health_orb_ring.py""", 0, False
Set WshShell = Nothing
