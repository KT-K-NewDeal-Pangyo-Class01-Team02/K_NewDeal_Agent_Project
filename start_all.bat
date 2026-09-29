@echo off
rem Double-click to start every Command Center server (see start_all.ps1).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_all.ps1" %*
pause
