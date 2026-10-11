@echo off
rem Build dist\Violet\Violet.exe with PyInstaller (ASCII only).
cd /d "%~dp0.."
python -m pip install -r requirements.txt -r requirements-build.txt || exit /b 1
if not exist web\dist\index.html (
  pushd web
  call npm install || exit /b 1
  call npm run build || exit /b 1
  popd
)
python tools\build_exe.py || exit /b 1
pause
