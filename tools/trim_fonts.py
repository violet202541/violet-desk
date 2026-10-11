#!/usr/bin/env python3
"""只打包界面真正用到的汇文明朝体分块。

汇文明朝体只用于我们自己写的标题（歌名、寄语和用户输入一律用霞鹜文楷，见 base.css 的 .title-text），
所以保留常用字分块（GB2312 一级字）和源码里出现过的字所在的分块，其余移到 tools/assets/huiwen-spare/，
不进安装包。改了界面文字后重新运行一次，需要的分块会自动搬回来。

  python tools/trim_fonts.py
"""
import glob
from pathlib import Path
import re
import shutil

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / 'web' / 'public' / 'fonts' / 'huiwen'
SPARE = ROOT / 'tools' / 'assets' / 'huiwen-spare'
CSS = ROOT / 'web' / 'src' / 'styles' / 'huiwen.css'
SPARE_CSS = SPARE / 'huiwen-all.css'
ALWAYS = 12  # chunks 000–012: basic Latin/punctuation and the 3,755 most common characters


def used_codepoints():
    text = ''.join(Path(p).read_text(encoding='utf-8') for p in glob.glob(str(ROOT / 'web' / 'src' / '**' / '*'), recursive=True)
                   if p.endswith(('.vue', '.js', '.css')) and 'huiwen.css' not in p)
    return {ord(c) for c in text if ord(c) > 0x2E7F}


def main():
    SPARE.mkdir(parents=True, exist_ok=True)
    full_css = SPARE_CSS.read_text(encoding='utf-8') if SPARE_CSS.exists() else CSS.read_text(encoding='utf-8')
    SPARE_CSS.write_text(full_css, encoding='utf-8')
    faces = re.findall(r'@font-face\s*\{.*?\}', full_css, flags=re.S)
    used = used_codepoints()
    kept, moved = [], 0
    for face in faces:
        name = re.search(r'(huiwen-\d+)\.woff2', face).group(1)
        here, spare = FONTS / f'{name}.woff2', SPARE / f'{name}.woff2'
        source = here if here.exists() else spare
        needed = int(name.split('-')[1]) <= ALWAYS or bool(set(TTFont(source).getBestCmap()) & used)
        if needed:
            if not here.exists():
                shutil.move(spare, here)
            kept.append(face)
        elif here.exists():
            shutil.move(here, spare)
            moved += 1
    licence = ''.join(line + '\n' for line in full_css.splitlines() if line.startswith('/*') and 'TerryWang' in line)
    header = licence + '/* 由 tools/trim_fonts.py 生成：只列出打包的分块，完整列表见 tools/assets/huiwen-spare/huiwen-all.css */\n'
    CSS.write_text(header + '\n'.join(kept) + '\n', encoding='utf-8')
    size = sum(p.stat().st_size for p in FONTS.glob('*.woff2')) / 1048576
    print(f'保留 {len(kept)} 个分块（{size:.1f} MB），移出 {moved} 个到 {SPARE.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
