@echo off
rem Usage: run.bat [options] <server_ip> <server_port>
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
    python main.py %*
) else (
    py -3 main.py %*
)
