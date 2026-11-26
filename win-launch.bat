@echo off
cd /d "%~dp0"

where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo Installation de uv en cours...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
)

uv run main.py
if %errorlevel% neq 0 pause
