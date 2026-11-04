@echo off
setlocal
set PYTHONDONTWRITEBYTECODE=1
"C:\Services\KaiqiuMatch_20260915\.venv\Scripts\python.exe" "%~dp0check_ai_access.py"
if errorlevel 1 echo Access diagnostics did not complete. Send this output ONLY, never your API key.
pause
