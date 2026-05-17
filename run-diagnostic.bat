@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  Sector Rotation Dashboard - Diagnostic launcher
echo ============================================================
echo.
echo Working folder: %CD%
echo.

echo --- Step 1: Check Python is installed ---
where python
if errorlevel 1 (
    echo.
    echo *** PROBLEM: Python is NOT on PATH ***
    echo.
    echo Fix: Install Python 3.10+ from https://www.python.org/downloads/
    echo During install, you MUST tick "Add python.exe to PATH" on the first screen.
    echo.
    echo If you already have Python installed, open a NEW PowerShell window and try:
    echo   python --version
    echo If that also fails, your Python isn't on PATH - reinstall with the checkbox.
    echo.
    pause
    exit /b 1
)
python --version
echo.

echo --- Step 2: Check pip ---
python -m pip --version
if errorlevel 1 (
    echo *** PROBLEM: pip is broken ***
    pause
    exit /b 1
)
echo.

echo --- Step 3: Create venv if missing ---
if not exist ".venv\Scripts\python.exe" (
    echo Creating .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo *** PROBLEM: venv creation failed ***
        pause
        exit /b 1
    )
    echo venv created.
) else (
    echo venv already exists.
)
echo.

echo --- Step 4: Install dependencies ---
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo *** PROBLEM: pip install failed - see messages above ***
    pause
    exit /b 1
)
echo.

echo --- Step 5: Check streamlit landed in the venv ---
.venv\Scripts\python.exe -c "import streamlit; print('streamlit', streamlit.__version__)"
if errorlevel 1 (
    echo *** PROBLEM: streamlit not importable ***
    pause
    exit /b 1
)
echo.

echo --- Step 6: Launching streamlit at http://localhost:8501 ---
echo This window stays open. Press Ctrl+C to stop.
echo.
.venv\Scripts\streamlit.exe run app.py
echo.

echo Streamlit exited.
pause
