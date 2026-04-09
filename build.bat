@echo off
REM Build script for Medical Opinion Management App (Windows)
REM Run this on a Windows machine with Python 3.9+ installed

echo ========================================
echo  Medical Opinion - Build Installer
echo ========================================
echo.

REM Step 1: Install dependencies
echo [1/4] Installing Python dependencies...
pip install -r requirements.txt
pip install pyinstaller
echo.

REM Step 2: Build with PyInstaller
echo [2/4] Building application with PyInstaller...
pyinstaller build.spec --noconfirm --clean
echo.

REM Step 3: Verify build
if not exist "dist\MedicalOpinion\MedicalOpinion.exe" (
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)
echo Build successful: dist\MedicalOpinion\MedicalOpinion.exe
echo.

REM Step 4: Create installer with Inno Setup (if available)
echo [3/4] Creating installer with Inno Setup...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    %ISCC% installer.iss
    echo.
    echo Installer created: installer_output\MedicalOpinion_Setup_1.0.0.exe
) else (
    echo Inno Setup not found. Install from: https://jrsoftware.org/isinfo.php
    echo Skipping installer creation. You can still use dist\MedicalOpinion\ directly.
)

echo.
echo [4/4] Done!
echo.
pause
