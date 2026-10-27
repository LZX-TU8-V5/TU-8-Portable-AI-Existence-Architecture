@echo off
set PYTHON=C:\Users\qq366410837\.workbuddy\binaries\python\versions\3.13.12\python.exe
set SCRIPT=D:\Program Files\QClaw\resources\openclaw\config\skills\qclaw-text-file\scripts\write_file.py
set SRC=C:\Users\qq366410837\AppData\Local\Temp\_tw_defense_log.md
set DST=D:\tu8-v5\defense-log.md

"%PYTHON%" "%SCRIPT%" --path "%DST%" --content-file "%SRC%" --platform windows --preserve

echo Exit code: %errorlevel%