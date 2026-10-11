@echo off
rem Violet launcher (ASCII only). Opens the desktop window without a console.
cd /d "%~dp0"
chcp 65001 >nul
python -c "import sys; assert sys.version_info >= (3, 10)" 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is required. Install Python and enable "Add to PATH".
  pause
  exit /b 1
)
python -c "import webview, mutagen, bs4, quickjs" 2>nul
if errorlevel 1 (
  echo Installing pywebview, mutagen, beautifulsoup4 and quickjs...
  python -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 (
    echo Install failed. Run: python -m pip install -r requirements.txt
    pause
    exit /b 1
  )
)
if not exist "%~dp0web\dist\index.html" (
  echo The interface has not been built. Run "npm install" and "npm run build" in the web folder.
  pause
  exit /b 1
)
where pythonw >nul 2>nul
if errorlevel 1 (
  python violet_app.py
  if errorlevel 1 pause
) else (
  start "" pythonw violet_app.py
)
