#!/usr/bin/env python3
"""从水彩紫罗兰生成应用图标与网页图标（需要 Pillow）。

- tools/violet.ico：16~256 多尺寸；小尺寸裁得更满、略提对比，任务栏上不发暗
- web/public/favicon.png、web/src/assets/violet-flower.png：界面里使用的同一朵花
"""
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path(__file__).with_name('assets') / 'violet-watercolor.png'


def square(image, fill):
    """Fit the flower into a square; `fill` is the share of the side it occupies."""
    side = max(image.size)
    canvas_side = int(side / fill)
    canvas = Image.new('RGBA', (canvas_side, canvas_side), (0, 0, 0, 0))
    canvas.alpha_composite(image, ((canvas_side - image.width) // 2, (canvas_side - image.height) // 2))
    return canvas


def tuned(image, size):
    small = size <= 48
    flower = image
    if small:
        rgb = flower.convert('RGB')
        rgb = ImageEnhance.Contrast(rgb).enhance(1.25)
        rgb = ImageEnhance.Color(rgb).enhance(1.25)
        rgb = ImageEnhance.Brightness(rgb).enhance(1.12)
        flower = Image.merge('RGBA', (*rgb.split(), flower.getchannel('A')))
    icon = square(flower, 0.98 if small else 0.9).resize((size, size), Image.LANCZOS)
    if small:
        icon = icon.filter(ImageFilter.UnsharpMask(radius=0.6, percent=80, threshold=1))
    return icon


def main():
    flower = Image.open(SOURCE).convert('RGBA')
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    frames = [tuned(flower, s) for s in sizes]
    frames[-1].save(Path(__file__).with_name('violet.ico'), sizes=[(s, s) for s in sizes], append_images=frames[:-1])
    tuned(flower, 128).save(ROOT / 'web' / 'public' / 'favicon.png')
    square(flower, 0.96).resize((256, 256), Image.LANCZOS).save(ROOT / 'web' / 'src' / 'assets' / 'violet-flower.png')
    print('图标已生成')


if __name__ == '__main__':
    main()
