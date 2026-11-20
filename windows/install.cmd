@echo off
rem Double-click to install mygns3theme (runs install.ps1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
pause
