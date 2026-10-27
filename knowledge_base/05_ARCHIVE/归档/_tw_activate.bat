@echo off
chcp 65001 >nul
echo ================================
echo  TU-8 一键激活脚本
echo ================================
echo.

:: Step 1: 恢复文件
echo [1/3] 恢复 C: workspace 文件...
powershell -ExecutionPolicy Bypass -Command "& { . 'D:\qq366410837\.qclaw\workspace\_tw_restore_v2.ps1' }"
echo.

:: Step 2: 写入激活指令到剪贴板
echo [2/3] 生成激活指令，已复制到剪贴板...
powershell -ExecutionPolicy Bypass -Command "Set-Clipboard -Value '你是 TU-8 框架。请执行：1) 读取 _agent_memory\00_state.md 恢复状态；2) 读取 _agent_memory\20_experiences.md 恢复经验；3) 报告当前状态。现在开始。'"
echo.

:: Step 3: 提示用户
echo [3/3] 完成！
echo.
echo ========================================
echo  请现在打开 OpenClaw 聊天框
echo  直接 Ctrl+V 粘贴，发送即可
echo ========================================
echo.
pause