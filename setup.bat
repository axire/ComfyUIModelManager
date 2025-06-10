@echo off
setlocal enabledelayedexpansion

:: Windows batch file for ComfyUI Model Manager setup
echo.
echo ===============================================
echo  ComfyUI Model Manager - Windows Setup
echo ===============================================
echo.

:: Set variables
set PYTHON_CMD=python
set VENV_DIR=venv

:: Check for Python
%PYTHON_CMD% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [INFO] Python found. Checking version...
%PYTHON_CMD% --version

:: Check if virtual environment exists
if exist "%VENV_DIR%" (
    echo [WARNING] Virtual environment '%VENV_DIR%' already exists.
) else (
    echo [INFO] Creating Python virtual environment...
    %PYTHON_CMD% -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate virtual environment and install requirements
echo [INFO] Installing dependencies in virtual environment...

:: Use the venv's pip directly
set VENV_PIP=%VENV_DIR%\Scripts\pip.exe
set VENV_PYTHON=%VENV_DIR%\Scripts\python.exe

if not exist "%VENV_PIP%" (
    echo [ERROR] Virtual environment seems incomplete. Try deleting '%VENV_DIR%' and running setup again.
    pause
    exit /b 1
)

echo [INFO] Installing packages from requirements.txt...
"%VENV_PIP%" install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    echo Try running: %VENV_DIR%\Scripts\activate.bat
    echo Then: pip install -r requirements.txt
    pause
    exit /b 1
)

echo [SUCCESS] Dependencies installed successfully.

:: Verify installation
echo [INFO] Verifying safetensors installation...
"%VENV_PYTHON%" -c "import safetensors; print('✓ safetensors import successful')" 2>nul
if %errorlevel% equ 0 (
    echo [SUCCESS] safetensors library is properly installed.
) else (
    echo [WARNING] safetensors library may not be properly installed.
)

:: Copy example config if it doesn't exist
if not exist "model_manager_config.json" (
    if exist "model_manager_config.example.json" (
        echo [INFO] Copying example configuration...
        copy "model_manager_config.example.json" "model_manager_config.json"
        echo [INFO] Please edit model_manager_config.json with your actual paths.
    )
)

echo.
echo ===============================================
echo  Setup Complete!
echo ===============================================
echo.
echo To run the application:
echo   start_model_manager.bat
echo.
echo Or manually:
echo   %VENV_DIR%\Scripts\activate.bat
echo   python model_manager.py
echo.
echo [IMPORTANT] For symbolic links to work on Windows:
echo - Run as Administrator (right-click, "Run as administrator")
echo - Or enable Developer Mode in Windows Settings
echo.
pause 