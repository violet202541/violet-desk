#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把音频文件内嵌的歌词导出成 .lrc 旁车文件（供 SirenX 等 iOS 播放器显示）。

原理：SirenX 等 iOS 播放器只认「与音频同目录同名的 .lrc 文件」，不读内嵌标签。
本脚本读取 FLAC:LYRICS / MP3:USLT / M4A:©lyr 标签里的歌词，写出同名 .lrc。

用法：
  python export_lrc.py               # 默认扫描 ./music
  python export_lrc.py 某文件夹      # 指定文件夹（递归）
"""

import glob
import os
import sys


def extract_lyrics(path):
    """读取音频文件内嵌歌词，返回文本或 None。"""
    import mutagen

    try:
        audio = mutagen.File(path)
    except Exception:
        return None
    if audio is None:
        return None

    if isinstance(audio, mutagen.flac.FLAC):
        vals = audio.get("LYRICS") or []
        return vals[0] if vals else None
    if isinstance(audio, mutagen.mp3.MP3):
        if audio.tags is None:
            return None
        frames = audio.tags.getall("USLT")
        return frames[0].text if frames else None
    if isinstance(audio, mutagen.mp4.MP4):
        vals = audio.get("\xa9lyr") or []
        return vals[0] if vals else None
    return None


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "./music"
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        print(f"目录不存在: {root}")
        sys.exit(1)

    exts = (".flac", ".mp3", ".m4a", ".aac")
    files = [f for f in glob.glob(os.path.join(root, "**", "*"), recursive=True)
             if f.lower().endswith(exts)]
    files.sort()
    if not files:
        print(f"{root} 下没有音频文件")
        return

    ok = skip = none = 0
    for f in files:
        lrc_path = os.path.splitext(f)[0] + ".lrc"
        if os.path.exists(lrc_path):
            skip += 1
            continue
        lyrics = extract_lyrics(f)
        if not lyrics:
            none += 1
            print(f"  无内嵌歌词: {os.path.relpath(f, root)}")
            continue
        with open(lrc_path, "w", encoding="utf-8") as fh:
            fh.write(lyrics)
        ok += 1
        print(f"  ✓ {os.path.relpath(lrc_path, root)}")

    print(f"\n完成：导出 {ok} 个，跳过(已有) {skip} 个，无内嵌歌词 {none} 个")
    if none:
        print("无内嵌歌词的歌曲可让 SirenX 走在线匹配，或重新下载该曲。")


if __name__ == "__main__":
    main()
