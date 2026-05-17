@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo First run - setting up. This takes about 2 minutes.
    python -m venv .venv || goto :err
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :err
)

echo Starting dashboard at http://localhost:8501 ...
.venv\Scripts\streamlit.exe run app.py
goto :end

:err
echo.
echo *** Setup failed. Double-click run-diagnostic.bat for details. ***
echo.

:end
pause
