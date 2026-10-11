#!/usr/bin/env python3
"""把生成好的图接入 Violet（需要 Pillow 与 numpy）。

把图放进 docs/art-inbox/，文件名以这些开头即可：
  logo*      → Grok bot 风格头像：侧栏 logo、窗口 / 任务栏 / exe 图标、网页图标
  hero-day*  → 白天的背景画（信笺主题）
  hero-night*→ 夜间的背景画（烛光主题，可选）
然后运行 python tools/import_art.py，再 cd web && npm run build。
同一类有多张时取最新的一张；也可以直接指定：python tools/import_art.py docs/art-inbox/logo-xxx.png

背景画会自动去掉纸色底（从左侧空白处取样），这样在浅色、深色两种纸上都能自然化开。
"""
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / 'docs' / 'art-inbox'
ASSETS = ROOT / 'web' / 'src' / 'assets'
ICON_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def newest(prefix):
    chosen = [Path(a) for a in sys.argv[1:] if Path(a).name.startswith(prefix)]
    if chosen:
        return chosen[-1]
    files = [p for p in INBOX.glob(prefix + '*') if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def rounded(image, radius_ratio=0.22):
    side = image.width
    mask = Image.new('L', (side * 4, side * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, side * 4 - 1, side * 4 - 1), radius=int(side * 4 * radius_ratio), fill=255)
    out = image.convert('RGBA')
    out.putalpha(Image.composite(out.getchannel('A'), Image.new('L', out.size, 0), mask.resize(out.size, Image.LANCZOS)))
    return out


def square(image):
    side = min(image.size)
    left, top = (image.width - side) // 2, (image.height - side) // 2
    return image.crop((left, top, left + side, top + side))


def import_logo(path):
    art = square(Image.open(path).convert('RGBA'))
    transparent = art.getchannel('A').getextrema()[0] < 250
    base = art if transparent else rounded(art)
    frames = []
    for size in ICON_SIZES:
        frame = base.resize((size, size), Image.LANCZOS)
        if size <= 48:  # small sizes: a touch more contrast so the capsule eyes stay crisp
            rgb = ImageEnhance.Contrast(frame.convert('RGB')).enhance(1.12)
            frame = Image.merge('RGBA', (*rgb.split(), frame.getchannel('A'))).filter(
                ImageFilter.UnsharpMask(radius=0.6, percent=70, threshold=1))
        frames.append(frame)
    frames[-1].save(ROOT / 'tools' / 'violet.ico', sizes=[(s, s) for s in ICON_SIZES], append_images=frames[:-1])
    base.resize((128, 128), Image.LANCZOS).save(ROOT / 'web' / 'public' / 'favicon.png')
    base.resize((256, 256), Image.LANCZOS).save(ASSETS / 'logo.png')
    print(f'logo  ← {path.name}：violet.ico、favicon.png、assets/logo.png')


def cut_paper(image):
    """Make the plain paper background transparent, sampling it from the empty left edge."""
    rgb = np.asarray(image.convert('RGB')).astype(float)
    sample = rgb[:, : max(40, rgb.shape[1] // 6)].reshape(-1, 3)
    paper = np.median(sample, axis=0)
    distance = np.sqrt(((rgb - paper) ** 2).sum(axis=2))
    alpha = np.clip((distance - 10) / 45, 0, 1)
    mask = Image.fromarray((alpha * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(1.2))
    out = image.convert('RGB')
    out.putalpha(mask)
    return out


def import_hero(path, name):
    image = Image.open(path)
    if image.width > 2000:
        image = image.resize((2000, round(image.height * 2000 / image.width)), Image.LANCZOS)
    cut_paper(image).save(ASSETS / f'{name}.webp', quality=82, method=6)
    print(f'{name} ← {path.name}')


def main():
    if not INBOX.is_dir():
        raise SystemExit(f'先建文件夹 {INBOX}，把图放进去')
    done = False
    if (path := newest('logo')):
        import_logo(path)
        done = True
    for name in ('hero-day', 'hero-night'):
        if (path := newest(name)):
            import_hero(path, name)
            done = True
    if not done:
        raise SystemExit('docs/art-inbox 里没有 logo* / hero-day* / hero-night* 开头的图片')
    print('完成。接着运行：cd web && npm run build')


if __name__ == '__main__':
    sys.exit(main())
