@echo off
setlocal
set PYTHONDONTWRITEBYTECODE=1
"C:\Services\KaiqiuMatch_20260915\.venv\Scripts\python.exe" "%~dp0install_growth.py"
if errorlevel 1 echo FAILED: send the complete output. Backup and rollback protect the existing application.
pause
