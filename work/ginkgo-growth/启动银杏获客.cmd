@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "C:\Users\User\AppData\Local\KaiqiuPython312\python.exe" (
  "C:\Users\User\AppData\Local\KaiqiuPython312\python.exe" "%~dp0launch_growth.py"
) else (
  py -3 launch_growth.py
)
if errorlevel 1 pause
