@echo off
rem Build dist\Violet-Setup-<version>.exe: the exe first, then the Inno Setup installer (ASCII only).
cd /d "%~dp0.."
python -m pip install -r requirements.txt -r requirements-build.txt || exit /b 1
if not exist web\dist\index.html (
  pushd web
  call npm install || exit /b 1
  call npm run build || exit /b 1
  popd
)
python tools\build_exe.py || exit /b 1
python tools\build_setup.py || exit /b 1
pause
