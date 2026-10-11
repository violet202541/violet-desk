#!/usr/bin/env python3
"""Draw the installer's wizard images: a sheet of Violet's paper with the watercolour violet, light and dark.

Large image 164x314 and small image 55x58 at 100% DPI, plus scaled copies; Inno Setup picks the closest size.
Output goes to build/installer (generated, not committed).
"""
from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build' / 'installer'
FLOWER = ROOT / 'tools' / 'assets' / 'violet-watercolor.png'
SCALES = (100, 125, 150, 175, 200, 250)
LARGE, SMALL = (164, 314), (55, 58)
THEMES = {
    'light': {'top': '#f6f0e5', 'bottom': '#e9dfcb', 'ink': '#5e3f8f', 'faint': '#8a7a66', 'rule': '#c9b99c', 'flower': 1.0},
    'dark': {'top': '#1c1825', 'bottom': '#141119', 'ink': '#c2abec', 'faint': '#9a8fae', 'rule': '#3a3248', 'flower': 0.92},
}


def script_font(size):
    """Pinyon Script, the app's own script face (from the web build); a system serif if it is missing."""
    found = sorted((ROOT / 'web' / 'dist' / 'assets').glob('pinyon-script-latin-400-normal-*.woff'))
    for path in [*found, Path('C:/Windows/Fonts/georgiai.ttf')]:
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            continue
    return ImageFont.load_default()


def serif_font(size):
    try:
        return ImageFont.truetype('C:/Windows/Fonts/georgiai.ttf', size)
    except OSError:
        return ImageFont.load_default()


def paper(size, theme, seed=7):
    w, h = size
    top, bottom = Image.new('RGB', (1, 1), theme['top']).getpixel((0, 0)), Image.new('RGB', (1, 1), theme['bottom']).getpixel((0, 0))
    sheet = Image.new('RGB', size)
    px = sheet.load()
    rng = random.Random(seed)
    for y in range(h):
        t = y / max(h - 1, 1)
        row = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
        for x in range(w):
            grain = rng.randint(-4, 4)
            px[x, y] = tuple(max(0, min(255, c + grain)) for c in row)
    return sheet.filter(ImageFilter.GaussianBlur(0.35))


def flower(width, turn, alpha=1.0, trim=False):
    img = Image.open(FLOWER).convert('RGBA')
    img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS).rotate(turn, Image.BICUBIC, expand=True)
    mask = img.getchannel('A')
    if trim:
        # The cut-out keeps a rim of the scan's white paper; on dark paper it glows, so pare it away.
        mask = mask.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(0.8))
    img.putalpha(mask.point(lambda a: round(a * alpha)))
    return img


def large(scale, theme):
    k = scale / 100
    w, h = round(LARGE[0] * k), round(LARGE[1] * k)
    img = paper((w, h), theme).convert('RGBA')
    # A postmark ring, faint, as if the sheet had travelled (drawn 4x and scaled down for smooth edges).
    ss = 4
    mark = Image.new('RGBA', (w * ss, h * ss), (0, 0, 0, 0))
    pen = ImageDraw.Draw(mark)
    cx, cy, r, line = w * 0.70 * ss, h * 0.14 * ss, w * 0.20 * ss, max(1, round(k * ss))
    for i in range(2):
        rr = r - i * 4 * k * ss
        pen.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=theme['rule'], width=line)
    for i in range(4):
        y = cy - r * 0.45 + i * r * 0.3
        pen.line((cx + r * 1.05, y, w * ss, y), fill=theme['rule'], width=line)
    img.alpha_composite(mark.resize((w, h), Image.LANCZOS))
    draw = ImageDraw.Draw(img)
    # The name, in Violet's hand.
    name = script_font(round(44 * k))
    draw.text((w * 0.13, h * 0.30), 'Violet', font=name, fill=theme['ink'])
    small = serif_font(round(9.5 * k))
    draw.text((w * 0.15, h * 0.30 + 52 * k), 'letters  ·  songs  ·  keepsakes', font=small, fill=theme['faint'])
    draw.line((w * 0.15, h * 0.30 + 68 * k, w * 0.62, h * 0.30 + 68 * k), fill=theme['rule'], width=max(1, round(k)))
    # The pressed violet, low on the sheet and slightly off-centre.
    bloom = flower(round(w * 0.92), 12, theme['flower'], trim=theme is THEMES['dark'])
    shadow = Image.new('RGBA', bloom.size, (40, 20, 50, 0))
    shadow.putalpha(bloom.getchannel('A').point(lambda a: round(a * 0.22)).filter(ImageFilter.GaussianBlur(5 * k)))
    x, y = round(w * 0.12), round(h - bloom.height + h * 0.04)
    img.alpha_composite(shadow, (x + round(3 * k), y + round(4 * k)))
    img.alpha_composite(bloom, (x, y))
    return img.convert('RGB')


def small(scale, theme):
    k = scale / 100
    w, h = round(SMALL[0] * k), round(SMALL[1] * k)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    bloom = flower(round(w * 0.98), -8, theme['flower'], trim=True)
    bloom.thumbnail((w, h), Image.LANCZOS)
    img.alpha_composite(bloom, ((w - bloom.width) // 2, (h - bloom.height) // 2))
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, theme in THEMES.items():
        for scale in SCALES:
            large(scale, theme).save(OUT / f'wizard-{name}-{scale}.png')
            small(scale, theme).save(OUT / f'small-{name}-{scale}.png')
    print(f'wizard images → {OUT}')


if __name__ == '__main__':
    main()
