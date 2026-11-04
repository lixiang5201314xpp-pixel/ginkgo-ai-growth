@echo off
setlocal
set PYTHONDONTWRITEBYTECODE=1
"C:\Services\KaiqiuMatch_20260915\.venv\Scripts\python.exe" "%~dp0install_growth_ai.py"
if errorlevel 1 echo FAILED: send the result ONLY. Never send your API key. Existing code is protected by backup and rollback.
pause
