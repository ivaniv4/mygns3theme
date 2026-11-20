@echo off
rem Double-click to remove mygns3theme (runs uninstall.ps1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
pause
