@echo off
rem ===========================================================================
rem  DO NOT EDIT without permission from the maintainer (Lee Seunghyun, EffortLEE1008).
rem  Keep the ONE-WINDOW behavior: all servers run in this window, and closing
rem  this window (or Ctrl+C) stops all of them. See root CLAUDE.md "start_all".
rem  To add an agent, edit command_center/agents.json ("server"), not this file.
rem ===========================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_all.ps1" %*
if errorlevel 1 pause
