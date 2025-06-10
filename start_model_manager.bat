@echo off
setlocal enabledelayedexpansion

:: Windows batch file for starting ComfyUI Model Manager
echo.
echo ===============================================
echo  ComfyUI Model Manager - Windows Launcher
echo ===============================================
echo.

set VENV_DIR=venv
set VENV_PYTHON=%VENV_DIR%\Scripts\python.exe

:: Check if virtual environment exists
if not exist "%VENV_PYTHON%" (
    echo [ERROR] Python executable not found in virtual environment.
    echo Please run setup.bat first to create the virtual environment.
    pause
    exit /b 1
)

:: Banner
echo.
echo By SOulsurf 2025-06-ihavenoclue
echo   ___           __      _   _ ___   __  __         _      _   __  __                                   
echo  / __^|___ _ __ / _^|_  _^| ^| ^| ^|_ _^| ^|  \/  ^|___  __^| ^|___ ^| ^| ^|  \/  ^|__ _ _ _  __ _ __ _ ___ _ _ 
echo ^| ^(__/ _ \ '  \  _^| ^|^| ^| ^|_^| ^|^| ^|^| ^|^|\/^|^| / _ \/ _` / -_^| ^| ^|^|\/^|^| / _` ^| ' \/ _` / _` / -_^) '_^|
echo  \___\___/_^|_^|_^|_^| \_,_^|\___/___^|_^|  ^|_^|\___/\__,_\___^|_^| ^|_^|  ^|_^|\__,_^|_^|_^|\__,_\__, \___^|_^|  
echo                                                                                     ^|___/          
echo  Manage repositories and model linking for ComfyUI. Ascii art is for wuzzes.
echo.

:: Check for Administrator privileges (for symbolic links)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Not running as Administrator.
    echo For symbolic link functionality, consider:
    echo - Right-click this file and "Run as administrator"
    echo - Or enable Developer Mode in Windows Settings
    echo.
)

:: Start the Model Manager
echo [INFO] Starting ComfyUI Model Manager...
echo [INFO] Using Python: %VENV_PYTHON%
echo.

"%VENV_PYTHON%" model_manager.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start the Model Manager.
    echo Check that all dependencies are installed.
    pause
    exit /b 1
)

:: This won't be reached due to the server running, but kept for reference
echo.
echo [INFO] ComfyUI Model Manager should now be running on http://localhost:8002
echo [INFO] Press Ctrl+C to stop the server.
echo.

:: Ask to open browser
set /p open_browser="Open Model Manager in browser now? (y/n): "
if /i "%open_browser%"=="y" (
    start http://localhost:8002
)

pause 