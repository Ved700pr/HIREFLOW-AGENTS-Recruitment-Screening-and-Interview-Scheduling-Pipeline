@echo off
REM Create .venv and install requirements (Windows cmd).  Usage: setup.bat   or   setup.bat dev
cd /d "%~dp0"
python -c "import sys; assert (3,10)<=sys.version_info[:2]<=(3,13), 'Unsupported Python '+sys.version.split()[0]+': use 3.10-3.13'" || exit /b 1
if not exist .venv python -m venv .venv || exit /b 1
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip || exit /b 1
python -m pip install -r requirements.txt || exit /b 1
if /i "%1"=="dev" python -m pip install -r requirements-dev.txt
if not exist .env copy .env.example .env >nul
echo.
echo Done. Activate with:  .venv\Scripts\activate
echo Then run:             streamlit run app.py
