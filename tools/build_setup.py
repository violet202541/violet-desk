#!/usr/bin/env python3
"""Build dist/Violet-Setup-<version>.exe from dist/Violet with Inno Setup 6.5+.

Run tools/build_exe.py first (or use tools/build_setup.bat, which does both).
Inno Setup: https://jrsoftware.org/isinfo.php, or `winget install JRSoftware.InnoSetup`.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / 'tools' / 'installer'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(INSTALLER))


def find_iscc():
    found = shutil.which('ISCC.exe') or shutil.which('ISCC')
    if found:
        return Path(found)
    for base in (os.environ.get('LOCALAPPDATA', '') + '/Programs', os.environ.get('ProgramFiles(x86)', ''),
                 os.environ.get('ProgramFiles', '')):
        candidate = Path(base) / 'Inno Setup 6' / 'ISCC.exe'
        if base and candidate.is_file():
            return candidate
    raise SystemExit('找不到 Inno Setup 6 的 ISCC.exe。安装：winget install JRSoftware.InnoSetup')


def with_bom(path):
    """Inno Setup reads .iss/.isl as UTF-8 only when they start with a BOM."""
    raw = path.read_bytes()
    if not raw.startswith(b'\xef\xbb\xbf'):
        path.write_bytes(b'\xef\xbb\xbf' + raw)


def main():
    from violet_core import APP_VERSION
    import make_wizard_art

    if not (ROOT / 'dist' / 'Violet' / 'Violet.exe').is_file():
        raise SystemExit('请先运行 python tools\\build_exe.py 生成 dist\\Violet')
    for name in ('violet.iss', 'ChineseSimplified.isl'):
        with_bom(INSTALLER / name)
    make_wizard_art.main()
    subprocess.run([str(find_iscc()), '/Qp', f'/DAppVersion={APP_VERSION}', str(INSTALLER / 'violet.iss')], check=True)
    setup = ROOT / 'dist' / f'Violet-Setup-{APP_VERSION}.exe'
    print(f'\n已生成：{setup}（{setup.stat().st_size / 1048576:.1f} MB）')


if __name__ == '__main__':
    main()
