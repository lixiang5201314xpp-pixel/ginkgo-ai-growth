@echo off
setlocal
set PYTHONDONTWRITEBYTECODE=1
"C:\Services\KaiqiuMatch_20260915\.venv\Scripts\python.exe" "%~dp0configure_ai.py"
if errorlevel 1 echo Please send the error message ONLY. Never send your API key.
pause
