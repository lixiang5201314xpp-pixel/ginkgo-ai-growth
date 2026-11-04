@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
"C:\Services\KaiqiuMatch_20260915\.venv\Scripts\python.exe" "%~dp0set_search_limit_20.py"
if errorlevel 1 echo FAILED: Send the error text only, without credentials.
pause
