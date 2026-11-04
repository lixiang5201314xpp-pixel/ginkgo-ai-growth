@echo off
setlocal
"C:\p312\python.exe" "%~dp0collect_growth_diagnostics.py"
if errorlevel 1 echo Diagnostic failed. Please send the error text.
pause
