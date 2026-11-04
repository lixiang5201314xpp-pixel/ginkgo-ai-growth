@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
"C:\Services\KaiqiuMatch_20260915\.venv\Scripts\python.exe" "%~dp0install_growth_workflow.py"
if errorlevel 1 echo FAILED: Send error text only, without any credentials. Existing service is protected by backup and rollback.
pause
