#!/usr/bin/env python3
"""构建前端字体资源（只需在更换字体时运行一次，产物已提交）。

1. 汇文明朝体 GBK（约 44MB TTF）按字频切成小块 woff2，配合 unicode-range 按需加载：
   GB2312 一级字 → 二级字 → 其余字符。生成 web/public/fonts/huiwen/*.woff2 与 web/src/styles/huiwen.css。
2. 从 Pinyon Script 提取「Violet」逐字母轮廓，生成 web/src/assets/wordmark.json，供开场书写动画使用。

用法：python tools/build_fonts.py path/to/汇文明朝体GBK.ttf
"""
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
import sys

from fontTools import subset
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'
OUT_FONTS = WEB / 'public' / 'fonts' / 'huiwen'
OUT_CSS = WEB / 'src' / 'styles' / 'huiwen.css'
OUT_WORDMARK = WEB / 'src' / 'assets' / 'wordmark.json'
PINYON = WEB / 'node_modules' / '@fontsource' / 'pinyon-script' / 'files' / 'pinyon-script-latin-400-normal.woff2'
FAMILY = 'Huiwen Mincho'

BASIC = [*range(0x20, 0x7F), *range(0xA0, 0x100), *range(0x2000, 0x2070), *range(0x2100, 0x2200),
         *range(0x2460, 0x2500), *range(0x25A0, 0x2700), *range(0x3000, 0x3040), *range(0xFF00, 0xFFF0)]


def gb_level(cp):
    try:
        raw = chr(cp).encode('gb2312')
    except UnicodeEncodeError:
        return None
    if len(raw) != 2:
        return None
    return 1 if 0xB0 <= raw[0] <= 0xD7 else 2 if 0xD8 <= raw[0] <= 0xF7 else None


def gb_key(cp):
    return chr(cp).encode('gb2312')


def chunked(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)]


def plan_chunks(cmap):
    available = set(cmap)
    basic = [cp for cp in BASIC if cp in available]
    taken = set(basic)
    level1 = sorted((cp for cp in available if cp not in taken and gb_level(cp) == 1), key=gb_key)
    level2 = sorted((cp for cp in available if cp not in taken and gb_level(cp) == 2), key=gb_key)
    taken |= set(level1) | set(level2)
    rest = sorted(cp for cp in available if cp not in taken)
    return [basic] + chunked(level1, 320) + chunked(level2, 420) + chunked(rest, 900)


def unicode_ranges(codepoints):
    ranges, start, prev = [], None, None
    for cp in sorted(codepoints):
        if start is None:
            start = prev = cp
        elif cp == prev + 1:
            prev = cp
        else:
            ranges.append((start, prev))
            start = prev = cp
    if start is not None:
        ranges.append((start, prev))
    return ', '.join(f'U+{a:X}' if a == b else f'U+{a:X}-{b:X}' for a, b in ranges)


def build_chunk(job):
    source, index, codepoints = job
    options = subset.Options()
    options.flavor = 'woff2'
    options.layout_features = ['*']
    options.hinting = False
    options.desubroutinize = True
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6]
    options.notdef_outline = False
    font = subset.load_font(source, options)
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)
    target = OUT_FONTS / f'huiwen-{index:03d}.woff2'
    subset.save_font(font, str(target), options)
    return index, target.stat().st_size


def build_huiwen(source):
    OUT_FONTS.mkdir(parents=True, exist_ok=True)
    for old in OUT_FONTS.glob('*.woff2'):
        old.unlink()
    cmap = TTFont(source, lazy=True).getBestCmap()
    chunks = plan_chunks(cmap)
    sizes = {}
    with ProcessPoolExecutor(max_workers=max(2, (os.cpu_count() or 4) - 1)) as pool:
        for index, size in pool.map(build_chunk, [(source, i, c) for i, c in enumerate(chunks)]):
            sizes[index] = size
    rules = ['/* 汇文明朝体 GBK · 开源且免费商用，禁止第三方以任何方式用此字体牟利。Font © 2022 TerryWang. */',
             '/* 由 tools/build_fonts.py 生成，请勿手改。 */']
    for index, codepoints in enumerate(chunks):
        rules.append('@font-face{font-family:"%s";font-style:normal;font-weight:400;font-display:swap;'
                     'src:url("/fonts/huiwen/huiwen-%03d.woff2") format("woff2");unicode-range:%s}'
                     % (FAMILY, index, unicode_ranges(codepoints)))
    OUT_CSS.parent.mkdir(parents=True, exist_ok=True)
    OUT_CSS.write_text('\n'.join(rules) + '\n', encoding='utf-8')
    total = sum(sizes.values())
    print(f'汇文明朝：{len(chunks)} 块，共 {total / 1048576:.1f} MB，首块 {sizes[0] / 1024:.0f} KB')


def build_wordmark(word='Violet'):
    font = TTFont(PINYON)
    cmap = font.getBestCmap()
    glyphs = font.getGlyphSet()
    hmtx = font['hmtx']
    kern = {}
    if 'GPOS' not in font and 'kern' in font:
        for table in font['kern'].kernTables:
            kern.update(table.kernTable)
    ascent = font['hhea'].ascent
    x = 0
    letters = []
    for ch in word:
        name = cmap[ord(ch)]
        pen = SVGPathPen(glyphs)
        # Flip Y so the path is in SVG coordinates (y grows downward), baseline at `ascent`.
        glyphs[name].draw(TransformPen(pen, (1, 0, 0, -1, x, ascent)))
        bounds = BoundsPen(glyphs)
        glyphs[name].draw(TransformPen(bounds, (1, 0, 0, -1, x, ascent)))
        letters.append({'char': ch, 'd': pen.getCommands(), 'bounds': bounds.bounds})
        x += hmtx[name][0]
    xs = [b for l in letters if l['bounds'] for b in (l['bounds'][0], l['bounds'][2])]
    ys = [b for l in letters if l['bounds'] for b in (l['bounds'][1], l['bounds'][3])]
    pad = 40
    view = [min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad]
    OUT_WORDMARK.parent.mkdir(parents=True, exist_ok=True)
    OUT_WORDMARK.write_text(json.dumps({'viewBox': [round(v) for v in view],
                                        'letters': [{'char': l['char'], 'd': l['d']} for l in letters]},
                                       ensure_ascii=False), encoding='utf-8')
    print(f'Wordmark：{word} → {OUT_WORDMARK.relative_to(ROOT)}')


if __name__ == '__main__':
    build_wordmark()
    if len(sys.argv) > 1:
        build_huiwen(sys.argv[1])
    else:
        print('未提供汇文明朝体 TTF 路径，跳过分块。')
