@echo off
cd /d "%~dp0"
echo Ginkgo official customer-service configuration 1.0.0
echo Credentials are entered only in the separate window. Do not send screenshots of keys.
"C:\Services\KaiqiuMatch_20260915\.venv\Scripts\python.exe" "%~dp0configure_channels.py"
if errorlevel 1 echo FAILED: Please report the error type only. Never send credentials.
pause
