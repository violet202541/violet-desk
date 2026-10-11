#!/usr/bin/env python3
"""打包 dist/Violet/Violet.exe（PyInstaller，目录模式）。

conda / mamba 环境把 OpenSSL、libffi 等运行库放在 Library/bin，PyInstaller 可能漏掉它们，
或从 PATH 上捡到其他程序自带的同名 DLL，导致 _ssl / _ctypes（pythonnet 依赖）载入失败。
这里显式打包当前解释器配套的版本；官方 python.org 解释器没有 Library/bin，不受影响。
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DLLS = ('libssl-*.dll', 'libcrypto-*.dll', 'ffi*.dll', 'libffi*.dll', 'liblzma*.dll', 'libbz2*.dll',
                'zlib*.dll', 'libexpat*.dll', 'sqlite3*.dll')


def conda_runtime_dlls():
    folder = Path(sys.prefix) / 'Library' / 'bin'
    if not folder.is_dir():
        return []
    return sorted({p for pattern in RUNTIME_DLLS for p in folder.glob(pattern) if p.suffix.lower() == '.dll'})


def main():
    if not (ROOT / 'web' / 'dist' / 'index.html').is_file():
        raise SystemExit('请先在 web 目录运行 npm install 与 npm run build')
    sep = ';' if sys.platform == 'win32' else ':'
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--name', 'Violet',
            '--icon', str(ROOT / 'tools' / 'violet.ico'),
            '--add-data', f'{ROOT / "web" / "dist"}{sep}web/dist',
            '--add-data', f'{ROOT / "tools" / "violet.ico"}{sep}tools',
            '--add-data', f'{ROOT / "data"}{sep}data',
            '--collect-submodules', 'webview',
            '--distpath', str(ROOT / 'dist'), '--workpath', str(ROOT / 'build'), '--specpath', str(ROOT / 'build'),
            str(ROOT / 'violet_app.py')]
    for dll in conda_runtime_dlls():
        args[3:3] = ['--add-binary', f'{dll}{sep}.']
    subprocess.run(args, check=True, cwd=ROOT)
    print(f'\n已生成：{ROOT / "dist" / "Violet" / "Violet.exe"}（分发时复制整个 dist/Violet 文件夹）')


if __name__ == '__main__':
    main()
