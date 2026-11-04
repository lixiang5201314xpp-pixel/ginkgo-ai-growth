@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
"C:\Services\KaiqiuMatch_20260915\.venv\Scripts\python.exe" "%~dp0install_growth_channels.py"
if errorlevel 1 echo FAILED: Please send the complete error text, without credentials. Backup and rollback protect existing service.
pause
