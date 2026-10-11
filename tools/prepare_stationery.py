"""把 assets/stationery 里生成好的原图压成应用用的 webp（web/src/assets/stationery）。

- 火漆：裁掉透明边，缩到 360px，保留透明。
- 邮票：竖版 2:3，缩到 420×630。
- 信纸：缩到 768px；接缝明显的几张，边缘与错开半张的自己交叉淡化，平铺时看不出接缝。
- 抬头：缩到 1200×400，保留透明。
原图保持不动；重跑会覆盖输出。
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'assets' / 'stationery'
OUT = ROOT / 'web' / 'src' / 'assets' / 'stationery'
BLEND = {'kraft', 'pressed-petals'}  # papers whose edges showed a seam when tiled


def seamless(image, feather=0.22):
    """Blend the tile with itself rolled by half near the edges, so the copies meet without a seam."""
    arr = np.asarray(image.convert('RGB')).astype(np.float32)
    h, w = arr.shape[:2]
    rolled = np.roll(np.roll(arr, h // 2, axis=0), w // 2, axis=1)
    ys = np.minimum(np.arange(h), h - 1 - np.arange(h)) / (h * feather)
    xs = np.minimum(np.arange(w), w - 1 - np.arange(w)) / (w * feather)
    keep = np.clip(np.minimum.outer(ys, xs), 0, 1)[..., None]
    keep = keep * keep * (3 - 2 * keep)  # smoothstep
    return Image.fromarray((arr * keep + rolled * (1 - keep)).astype(np.uint8))


def main():
    for folder in ('wax', 'stamps', 'paper', 'letterhead'):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    for path in sorted((SRC / 'wax').glob('*.png')):
        im = Image.open(path).convert('RGBA')
        im = im.crop(im.getchannel('A').point(lambda a: 255 if a > 8 else 0).getbbox())
        im.thumbnail((360, 360), Image.LANCZOS)
        im.save(OUT / 'wax' / f'{path.stem}.webp', 'WEBP', quality=90, method=6)
    for path in sorted((SRC / 'stamps').glob('*.png')):
        im = Image.open(path).convert('RGB').resize((420, 630), Image.LANCZOS)
        im.save(OUT / 'stamps' / f'{path.stem}.webp', 'WEBP', quality=86, method=6)
    for path in sorted((SRC / 'paper').glob('*.png')):
        # Laid paper has straight chain lines that blending would double; it already tiles well enough.
        im = Image.open(path).convert('RGB')
        im = (seamless(im) if path.stem in BLEND else im).resize((768, 768), Image.LANCZOS)
        im.save(OUT / 'paper' / f'{path.stem}.webp', 'WEBP', quality=84, method=6)
    for path in sorted((SRC / 'letterhead').glob('*.png')):
        im = Image.open(path).convert('RGBA').resize((1200, 400), Image.LANCZOS)
        im.save(OUT / 'letterhead' / f'{path.stem}.webp', 'WEBP', quality=90, method=6)
    total = sum(p.stat().st_size for p in OUT.rglob('*.webp'))
    print(f'{len(list(OUT.rglob("*.webp")))} files, {total / 1024:.0f} KB → {OUT}')


if __name__ == '__main__':
    main()
