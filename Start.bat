@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 -m gtnh_migrator
) else (
  python -m gtnh_migrator
)
if errorlevel 1 pause
