@echo off
setlocal

REM Windows build helper for Gravity Runner (Pygame -> exe via PyInstaller)

if not exist venv (
  python -m venv venv
)

call venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt

pyinstaller --noconsole --onefile --add-data "assets;assets" main.py

echo.
echo Build finished. Check the "dist" folder.
pause

