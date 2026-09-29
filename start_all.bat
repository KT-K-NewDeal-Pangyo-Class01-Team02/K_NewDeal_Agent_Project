@echo off
rem Double-click to start every Command Center server in THIS window.
rem Close this window (or press Ctrl+C) to stop all of them. See start_all.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_all.ps1" %*
if errorlevel 1 pause
