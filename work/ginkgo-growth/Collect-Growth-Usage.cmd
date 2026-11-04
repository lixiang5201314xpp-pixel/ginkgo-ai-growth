@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
"C:\p312\python.exe" "%~dp0collect_workflow_usage.py"
if errorlevel 1 echo FAILED: Please send the error text only.
echo Read-only diagnostics completed. No API calls, restart or customer messages.
pause
