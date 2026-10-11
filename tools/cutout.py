#!/usr/bin/env python3
"""从水彩扫描件里抠出一朵花：按与纸色的色差生成透明度，只保留与中心连通的区域。

用法：python tools/cutout.py in.jpg x0 y0 x1 y1 out.png
"""
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def cutout(path, box, low=20, high=58):
    image = Image.open(path).convert('RGB').crop(box)
    arr = np.asarray(image).astype(np.float32)
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    paper = np.median(border, axis=0)
    dist = np.sqrt(((arr - paper) ** 2).sum(axis=2))
    alpha = np.clip((dist - low) / (high - low), 0, 1)
    # Keep only the blob connected to the centre (drop neighbouring leaves and stems).
    solid = Image.fromarray(((alpha > 0.35) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    cx, cy = solid.width // 2, solid.height // 2
    marker = 128
    ImageDraw.floodfill(solid, (cx, cy), marker)
    keep = (np.asarray(solid) == marker).astype(np.uint8) * 255
    # Fill holes: pale petal patches close to the paper colour belong to the flower.
    outside = Image.fromarray(255 - keep)
    padded = Image.new('L', (outside.width + 2, outside.height + 2), 255)
    padded.paste(outside, (1, 1))
    ImageDraw.floodfill(padded, (0, 0), 64)
    inside = (np.asarray(padded)[1:-1, 1:-1] != 64).astype(np.uint8) * 255
    body = np.asarray(Image.fromarray(inside).filter(ImageFilter.MinFilter(9))
                      .filter(ImageFilter.GaussianBlur(3))).astype(np.float32) / 255
    keep = np.asarray(Image.fromarray(inside).filter(ImageFilter.MaxFilter(5))
                      .filter(ImageFilter.GaussianBlur(2))).astype(np.float32) / 255
    alpha = np.maximum(alpha, body) * keep
    rgba = np.dstack([arr, alpha * 255]).astype(np.uint8)
    out = Image.fromarray(rgba, 'RGBA')
    return out.crop(out.getbbox())


if __name__ == '__main__':
    src, x0, y0, x1, y1, dst = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
    cutout(src, (x0, y0, x1, y1)).save(dst)
    print(dst)
