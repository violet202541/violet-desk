#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChKSz 音乐下载工具

利用 ChKSz 第三方音乐聚合 API (https://api.chksz.com) 搜索歌曲、解析音频直链并下载。
支持三个平台：网易云(netease) / QQ音乐(qq) / 酷狗(kugou)。

依赖：仅 Python 3 标准库，无需 pip 安装任何东西。

用法示例：
  python chksz_dl.py check                       # 验证 API Key 是否有效，并显示剩余额度
  python chksz_dl.py search netease 晴天         # 搜索
  python chksz_dl.py url netease 186016 -q lossless   # 打印音频直链（可粘贴到其他工具）
  python chksz_dl.py download netease 186016 -q lossless -o ./music
  python chksz_dl.py find netease 晴天 -o ./music     # 搜索 -> 交互选择多首 -> 下载
  python chksz_dl.py playlist 2831553045 -o ./music   # 下载整个网易云歌单

API Key 获取优先级：--key 参数 > 环境变量 CHKSZ_API_KEY > 配置文件。
配置文件默认 ~/.chksz_key（首行为 key），或脚本目录下 ./.chksz_key。
"""

import argparse
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.chksz.com"
TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) chksz-dl/1.0"
KEY_FILE = os.path.join(os.path.expanduser("~"), ".chksz_key")
_API_CONTEXT = ContextVar("chksz_api_context", default=(None, None))


class ApiError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class DownloadCancelled(RuntimeError):
    pass


@contextmanager
def api_session(on_quota=None, cancel=None):
    """Thread-local response observer and cooperative cancellation for TUI workers."""
    token = _API_CONTEXT.set((on_quota, cancel))
    try:
        yield
    finally:
        _API_CONTEXT.reset(token)


def check_cancel(cancel=None):
    cancel = cancel if cancel is not None else _API_CONTEXT.get()[1]
    if cancel is not None and cancel.is_set():
        raise DownloadCancelled("已取消")

# 平台音质档位（高 -> 低），用于自动降级
NETEASE_LEVELS = ["jymaster", "sky", "jyeffect", "hires", "lossless", "exhigh", "standard"]
QQ_KUGOU_SIZES = ["master", "hires", "flac", "320k", "128k"]

PLATFORM_ALIASES = {
    "netease": "netease", "163": "netease", "网易": "netease", "网易云": "netease",
    "qq": "qq", "qqmusic": "qq", "企鹅": "qq",
    "kugou": "kugou", "kg": "kugou", "酷狗": "kugou",
}


# ---------------------------------------------------------------- HTTP 基础

def api(path, params, key, retries=3):
    """GET ChKSz 接口，返回 (JSON, 响应头)。429 限流时自动退避重试。"""
    params = dict(params)
    params["apikey"] = key
    url = BASE_URL + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        check_cancel()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                headers = dict(resp.headers)
                body = json.loads(resp.read().decode("utf-8", "replace"))
                if not isinstance(body, dict):
                    raise ApiError("接口返回了非对象 JSON")
                observer, _ = _API_CONTEXT.get()
                if observer:
                    observer(headers)
                return body, headers
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                retry_after = e.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else 5 * (attempt + 1)
                wait = min(wait, 60)
                _, cancel = _API_CONTEXT.get()
                if cancel is not None:
                    if cancel.wait(wait):
                        raise DownloadCancelled("已取消")
                else:
                    time.sleep(wait)
                continue
            if e.code == 401:
                raise ApiError("API Key 无效（401）。请检查 Key 配置", 401) from None
            if e.code == 402:
                raise ApiError("额度已用尽（402），请稍后再试或更换 Key", 402) from None
            if e.code == 403:
                raise ApiError("请求被拒绝（403），可能触发了限流或该 Key 无权限", 403) from None
            detail = e.read().decode('utf-8', 'replace')[:300].replace(key, "[KEY]")
            try:
                detail = json.loads(detail).get("msg") or detail
            except (ValueError, AttributeError):
                pass
            if e.code == 503:
                raise ApiError(f"平台暂不可用（503）：{detail}", e.code) from None
            raise ApiError(f"HTTP {e.code}：{detail}", e.code) from None
        except urllib.error.URLError as e:
            raise ApiError(f"网络错误：{e.reason}") from None
        except (ValueError, TimeoutError) as e:
            raise ApiError("接口返回无效 JSON 或请求超时，请重试") from None


def check_business(body):
    """校验 {code:200, msg:'success'} 的业务包装。"""
    if body.get("code") != 200 or body.get("msg") != "success":
        raise ApiError(f"业务错误：code={body.get('code')} msg={body.get('msg')}", body.get("code"))


def header_get(headers, name):
    """大小写无关地读取响应头。"""
    lower = name.lower()
    for k, v in headers.items():
        if k.lower() == lower:
            return v
    return None


def stream_download(url, out_path, progress=None, cancel=None):
    """Download to a unique temporary file; publish only a complete, nonempty file.

    Windows rename and POSIX hard-link publication refuse to overwrite a target,
    including one created by a concurrent download. No partial audio is exposed.
    """
    check_cancel(cancel)
    if os.path.exists(out_path):
        raise FileExistsError(out_path)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Referer": BASE_URL + "/",
    })
    temp_path = None
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            content_type = header_get(resp.headers, "Content-Type") or ""
            if any(t in content_type.lower() for t in ("text/html", "application/json", "text/plain")):
                raise RuntimeError("下载地址返回了错误页面，未保存为音频")
            raw_length = header_get(resp.headers, "Content-Length") or "0"
            total = int(raw_length) if str(raw_length).isdigit() else 0
            done = 0
            with tempfile.NamedTemporaryFile(mode="wb", prefix=".violet-", suffix=".part",
                                             dir=os.path.dirname(os.path.abspath(out_path)),
                                             delete=False) as f:
                temp_path = f.name
                while True:
                    check_cancel(cancel)
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
            check_cancel(cancel)
            if not done or (total and done != total):
                raise RuntimeError("音频下载不完整，请重试")
            if os.name == "nt":
                # Unlike POSIX rename, Windows rename refuses an existing target.
                # It also works on removable filesystems without hard-link support.
                os.rename(temp_path, out_path)
                temp_path = None
            else:
                os.link(temp_path, out_path)
            return done
    finally:
        if temp_path is not None:
            os.unlink(temp_path)


def http_get(url, out_path, show_progress=True):
    """流式下载到文件，CLI 模式下打印进度。"""
    is_tty = show_progress and sys.stdout.isatty()

    def _progress(done, total):
        if is_tty and total:
            pct = done * 100 // total
            sys.stdout.write(f"\r  {done / 1048576:6.1f} / {total / 1048576:6.1f} MB  {pct:3d}%")
            sys.stdout.flush()

    size = stream_download(url, out_path, progress=_progress if show_progress else None)
    if is_tty:
        sys.stdout.write("\n")
    return size


# ---------------------------------------------------------------- Key 管理

def resolve_key(cli_key):
    if cli_key:
        return cli_key
    env = os.environ.get("CHKSZ_API_KEY")
    if env:
        return env.strip()
    for path in (KEY_FILE, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chksz_key")):
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        return line
    return None


def prompt_key():
    key = input("请输入 ChKSz API Key (chksz_...): ").strip()
    if not key.startswith("chksz_"):
        raise RuntimeError("Key 必须以 chksz_ 开头")
    save = input("保存到 ~/.chksz_key 以便下次直接使用？[y/N]: ").strip().lower()
    if save in ("y", "yes"):
        with open(KEY_FILE, "w", encoding="utf-8") as f:
            f.write(key + "\n")
        print(f"已保存到 {KEY_FILE}")
    return key


# ---------------------------------------------------------------- 平台实现

def search_netease(key, keyword, limit=20, offset=0):
    body, _ = api("/api/163_search", {"keyword": keyword, "limit": limit, "offset": offset}, key)
    check_business(body)
    data = body["data"]
    songs = []
    entries = data if isinstance(data, list) else data.get("songs", [])
    for s in entries:
        songs.append({
            "id": str(s["id"]),
            "name": s.get("name", ""),
            "artist": s.get("artists", ""),
            "album": s.get("album", ""),
            "picUrl": s.get("picUrl", ""),
            "duration": s.get("duration", 0),
        })
    return songs


def resolve_netease(key, sid, level):
    body, _ = api("/api/163_music", {"id": sid, "level": level, "type": "json"}, key)
    check_business(body)
    d = body["data"]
    return {"url": d.get("url"), "level": d.get("level"), "br": d.get("br"), "picUrl": d.get("picUrl")}


def search_qq(key, keyword, num=10):
    try:
        body, _ = api("/api/qq_music", {"msg": keyword, "num": num, "type": "json"}, key)
    except ApiError as e:
        if e.status == 404:  # 上游以 404 表示「未找到匹配的歌曲」
            return []
        raise
    if body.get("code") not in (None, 200):
        raise ApiError(f"QQ 搜索失败：{body.get('msg') or body.get('code')}", body.get("code"))
    items = []
    for i in body.get("list", []):
        items.append({
            "id": str(i.get("mid", "")),
            "name": i.get("name", ""),
            "artist": i.get("singer", ""),
            "album": i.get("album", ""),
            "pay": i.get("pay", ""),
            "picUrl": i.get("cover") or i.get("picUrl") or "",
            "duration": i.get("duration", 0),
            "n": i.get("n", 0),
        })
    return items


def resolve_qq(key, mid, size):
    body, _ = api("/api/qq_music", {"mid": mid, "size": size, "type": "json"}, key)
    check_business(body)
    return {"url": body.get("url"), "format": body.get("format"), "lrc": body.get("lrc"),
            "cover": body.get("cover"), "name": body.get("name"), "singer": body.get("singer")}


def search_kugou(key, keyword):
    try:
        body, _ = api("/api/kugou_music", {"msg": keyword, "type": "json"}, key)
    except ApiError as e:
        if e.status == 404:
            return []
        raise
    check_business(body)
    items = []
    for i in body.get("list", []):
        items.append({
            "id": str(i.get("id", "")),
            "name": i.get("name", ""),
            "artist": i.get("singer", ""),
            "album": i.get("album", ""),
            # ChKSz documents Kugou duration in seconds; UI uses milliseconds.
            "duration": int(float(i.get("duration") or 0) * 1000),
            "n": i.get("n", 0),
        })
    return items


def resolve_kugou(key, kid, size):
    body, _ = api("/api/kugou_music", {"id": kid, "size": size, "type": "json"}, key)
    check_business(body)
    return {"url": body.get("url"), "format": body.get("format"), "lrc": body.get("lrc"),
            "cover": body.get("cover"), "name": body.get("name"), "singer": body.get("singer")}


# 平台分发表
SEARCH = {"netease": search_netease, "qq": search_qq, "kugou": search_kugou}
RESOLVE = {"netease": resolve_netease, "qq": resolve_qq, "kugou": resolve_kugou}
PLATFORM_LABEL = {"netease": "网易云", "qq": "QQ", "kugou": "酷狗"}


def search_all(key, keyword, per_platform=10, on_error=None):
    """聚合搜索三平台，结果带 platform 字段。单个平台失败不影响其他。

    若三平台全部失败（如 Key 无效），抛出第一个平台的错误。
    """
    results = []
    errors = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {p: pool.submit(copy_context().run, SEARCH[p], key, keyword)
                   for p in ("netease", "qq", "kugou")}
        for platform, future in pending.items():
            try:
                songs = future.result()
            except DownloadCancelled:
                raise
            except Exception as e:
                message = f"{PLATFORM_LABEL.get(platform, platform)}: {e}"
                errors.append(message)
                if on_error:
                    on_error(message)
                continue
            for s in songs[:per_platform]:
                s["platform"] = platform
                results.append(s)
    if not results and errors:
        raise RuntimeError(errors[0])
    return results


# ---------------------------------------------------------------- QQ 歌单（公开接口，无需登录）

def qq_playlist_page(playlist_id, song_begin=0, song_num=500):
    """拉取一页 QQ 歌单（musicu.fcg 公开接口）。返回 data 部分 dict。

    无需登录即可读取公开歌单。每页最多约 500 首，用 song_begin 翻页。
    歌曲字段：mid / name / singer[].name / album.name / interval(秒)。
    """
    payload = json.dumps({
        "req_0": {
            "module": "music.srfDissInfo.aiDissInfo",
            "method": "uniform_get_Dissinfo",
            "param": {"disstid": int(playlist_id), "userinfo": 0, "orderlist": 1,
                      "song_begin": song_begin, "song_num": song_num},
        },
        "comm": {"ct": 24, "cv": 0, "uin": 0},
    }, ensure_ascii=False)
    url = "https://u.y.qq.com/cgi-bin/musicu.fcg?" + urllib.parse.urlencode(
        {"format": "json", "data": payload})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"拉取 QQ 歌单失败：{e.reason}")
    r = body.get("req_0") or {}
    if r.get("code") not in (0, None):
        raise RuntimeError(f"QQ 接口错误：code={r.get('code')} msg={r.get('msg')}")
    return r.get("data") or {}


def fetch_qq_playlist(playlist_id):
    """分页拉取 QQ 歌单全部歌曲。返回 (歌单信息 dict, 歌曲 list)。"""
    info, songs = {}, []
    page = 0
    while True:
        check_cancel()
        data = qq_playlist_page(playlist_id, song_begin=page * 500, song_num=500)
        if page == 0:
            info = data.get("dirinfo") or {}
        page_songs = data.get("songlist") or []
        songs.extend(page_songs)
        total = data.get("total_song_num") or 0
        if not page_songs or len(page_songs) < 500 or len(songs) >= total:
            break
        page += 1
    return info, songs


def normalize_qq_tracks(songs):
    """把 QQ 歌单原始歌曲条目转成与 search 结果一致的 dict。"""
    out = []
    for t in songs:
        singers = ", ".join(s.get("name", "") for s in t.get("singer") or [])
        album = t.get("album") or {}
        out.append({
            "id": t.get("mid") or "",
            "name": t.get("name") or "",
            "artist": singers,
            "album": album.get("name", ""),
            "album_mid": album.get("mid", ""),  # 供 TUI 拼封面 CDN 直链（不耗额度）
            "duration": (t.get("interval") or 0) * 1000,  # 秒 -> 毫秒
        })
    return out


def parse_playlist_id(raw):
    """从纯数字、/playlist/{id}、id={id} 等常见格式里提取歌单 ID。"""
    raw = raw.strip()
    if raw.isdigit():
        return raw
    for pat in (r"(?:[?&#]|^)(?:id|disstid|ADTAG_playlistid)=(\d+)", r"/playlist/(\d+)"):
        m = re.search(pat, raw)
        if m:
            return m.group(1)
    raise RuntimeError("无法识别歌单 ID，请提供纯数字 ID 或完整歌单链接")


# ---------------------------------------------------------------- 网易云歌单（走 ChKSz，需 Key）

def _normalize_netease_track(t):
    """把网易云歌单原始 track 转成与 search 结果一致的 dict。"""
    al = t.get("al") or {}
    return {
        "id": str(t.get("id")),
        "name": t.get("name", ""),
        "artist": ", ".join(a.get("name", "") for a in t.get("ar") or []),
        "album": al.get("name", ""),
        "picUrl": al.get("picUrl", ""),  # 封面直链，供 TUI 预览（走 CDN，不耗额度）
        "duration": t.get("dt") or 0,  # 毫秒
    }


def fetch_netease_playlist(key, pid):
    """拉取网易云歌单。返回 (歌单信息 dict, 歌曲 list)，与 fetch_qq_playlist 同形。"""
    body, _ = api("/api/163_playlist", {"id": pid}, key)
    check_business(body)
    data = body["data"]
    info = {"name": data.get("name"), "trackCount": data.get("trackCount")}
    tracks = [_normalize_netease_track(t) for t in data.get("tracks", [])]
    return info, tracks


# ---------------------------------------------------------------- 工具函数

def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(name)).strip().rstrip(". ")
    if not name:
        return "untitled"
    if re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", name.split(".")[0], re.I):
        name = "_" + name
    # Keep individual Windows path components comfortably below 255 characters.
    return name[:100].rstrip(". ")


def guess_ext(url, fmt=None):
    """根据 URL 路径后缀或 format 字段推断文件扩展名。"""
    if fmt and re.fullmatch(r"[a-z0-9]+", fmt.lower()):
        return "." + fmt.lower()
    path = urllib.parse.urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in (".mp3", ".flac", ".m4a", ".wav", ".aac", ".ogg", ".ape", ".wma", ".opus"):
        return ext
    return ".mp3"


def http_get_bytes(url):
    """GET 并返回二进制内容（用于下载封面图）。"""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def netease_lyrics_text(key, sid):
    """获取网易云歌词文本（原文+翻译，qmdec 同款拼接：lrc + '\\n' + tlyric）。"""
    body, _ = api("/api/163_lyric", {"id": sid}, key)
    check_business(body)
    data = body.get("data", {})
    lrc = data.get("lrc") or ""
    tlyric = data.get("tlyric") or ""
    if lrc and tlyric:
        return lrc.rstrip() + "\n" + tlyric.rstrip()
    return lrc or tlyric or None


def embed_metadata(path, meta=None, lyrics=None, cover_bytes=None):
    """仿 qmdec：把歌词和封面内嵌进音频文件标签（FLAC/MP3/M4A），单文件自包含。

    - 歌词 → FLAC:LYRICS / MP3:USLT / M4A:©lyr
    - 封面 → FLAC:PICTURE / MP3:APIC / M4A:covr
    - 歌名/歌手/专辑若提供则一并写入。
    """
    import mutagen
    from mutagen.flac import FLAC
    from mutagen.mp3 import MP3
    from mutagen.mp4 import MP4
    meta = meta or {}
    try:
        audio = mutagen.File(path)
        if audio is None:
            return False
        title = meta.get("title")
        artist = meta.get("artist")
        album = meta.get("album")

        if isinstance(audio, FLAC):
            if title:
                audio["TITLE"] = title
            if artist:
                audio["ARTIST"] = artist
            if album:
                audio["ALBUM"] = album
            if lyrics:
                audio["LYRICS"] = lyrics
            if cover_bytes:
                from mutagen.flac import Picture
                pic = Picture()
                pic.type = 3  # front cover
                pic.mime = "image/jpeg"
                pic.data = cover_bytes
                audio.add_picture(pic)
        elif isinstance(audio, MP3):
            from mutagen.id3 import APIC, TALB, TIT2, TPE1, USLT
            if audio.tags is None:
                audio.add_tags()  # 无 ID3 标签时先创建
            if title:
                audio.tags.add(TIT2(encoding=3, text=[title]))
            if artist:
                audio.tags.add(TPE1(encoding=3, text=[artist]))
            if album:
                audio.tags.add(TALB(encoding=3, text=[album]))
            if lyrics:
                audio.tags.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))
            if cover_bytes:
                audio.tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="", data=cover_bytes))
        elif isinstance(audio, MP4):
            if title:
                audio["\xa9nam"] = [title]
            if artist:
                audio["\xa9ART"] = [artist]
            if album:
                audio["\xa9alb"] = [album]
            if lyrics:
                audio["\xa9lyr"] = [lyrics]
            if cover_bytes:
                from mutagen.mp4 import MP4Cover
                audio["covr"] = [MP4Cover(cover_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
        else:
            return False
        audio.save()
        return True
    except Exception:
        return False


def embed_song_data(key, path, platform, song, lrc=None, pic_url=None,
                    want_lyric=True, want_cover=True, sidecar_lrc=False):
    """仿 qmdec：下载完成后把歌词和封面内嵌进文件。返回标志串。

    sidecar_lrc=True 时（手机版/iOS 兼容），额外写出同名 .lrc 旁车文件，
    供 SirenX 等只认 .lrc 的播放器显示歌词。
    """
    lyrics = None
    cover = None
    if want_lyric:
        if platform == "netease":
            try:
                lyrics = netease_lyrics_text(key, song["id"])
            except Exception:
                lyrics = None
        else:
            lyrics = lrc
    if want_cover and pic_url:
        try:
            cover = http_get_bytes(pic_url)
        except Exception:
            cover = None

    marks = []
    if want_lyric and not lyrics:
        marks.append("无可用歌词")
    if want_cover and not cover:
        marks.append("无可用封面")
    if sidecar_lrc and lyrics:
        try:
            with open(os.path.splitext(path)[0] + ".lrc", "w", encoding="utf-8") as f:
                f.write(lyrics)
            marks.append("lrc")
        except Exception:
            pass
    meta = {"title": song.get("name"), "artist": song.get("artist"), "album": song.get("album")}
    if meta or lyrics or cover:
        if embed_metadata(path, meta=meta, lyrics=lyrics, cover_bytes=cover):
            if lyrics:
                marks.append("内嵌歌词")
            if cover:
                marks.append("内嵌封面")
        else:
            marks.append("标签未写入，音频已保存")
    return " +".join(marks)


def parse_quota(headers):
    """从响应头解析额度信息，返回 dict。"""
    quota = {}
    for key in ("X-Quota-Free-Remaining", "X-Quota-Paid-Remaining", "X-RateLimit-Limit"):
        raw = header_get(headers, key)
        if raw is not None and str(raw).isdigit():
            quota[key] = int(raw)
    return quota


def print_quota(headers):
    quota = parse_quota(headers)
    parts = []
    if "X-Quota-Free-Remaining" in quota:
        parts.append(f"免费剩余: {quota['X-Quota-Free-Remaining']}")
    if "X-Quota-Paid-Remaining" in quota:
        parts.append(f"付费剩余: {quota['X-Quota-Paid-Remaining']}")
    if "X-RateLimit-Limit" in quota:
        parts.append(f"限流: {quota['X-RateLimit-Limit']}")
    if parts:
        print("  额度信息: " + " | ".join(parts))
    return quota


def print_song(i, s, show_id=True):
    dur = s.get("duration") or 0
    mins = dur // 60000
    secs = (dur % 60000) // 1000
    extra = ""
    if "pay" in s and s["pay"]:
        extra = f"  [{s['pay']}]"
    dur_str = f"  {mins}:{secs:02d}" if dur else ""
    sid = f"  id={s['id']}" if show_id else ""
    print(f"  {i:>3}. {s['name']} - {s['artist']}  《{s['album']}》{dur_str}{sid}{extra}")


def pick_indices(max_n):
    """交互式输入序号，支持 1,3,5 或 1-3 或全部(a) 或回车跳过。"""
    try:
        raw = input(f"  输入要下载的序号（可逗号/空格/连字符组合，如 1,3 5-7；a=全部；回车跳过）: ").strip()
    except EOFError:
        return []
    if not raw:
        return []
    if raw.lower() in ("a", "all", "*"):
        return list(range(max_n))
    picks = set()
    for part in re.split(r"[,，\s]+", raw):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                picks.update(range(int(a) - 1, int(b)))
            except ValueError:
                pass
        else:
            try:
                picks.add(int(part) - 1)
            except ValueError:
                pass
    return sorted(p for p in picks if 0 <= p < max_n)


# ---------------------------------------------------------------- 子命令

def cmd_check(args, key):
    body, headers = api("/api/163_search", {"keyword": "晴天", "limit": 1, "offset": 0}, key)
    check_business(body)
    print("✓ API Key 有效")
    print_quota(headers)
    if getattr(args, "dump", False):
        print("\n全部响应头（检查额度来源）:")
        for k, v in sorted(headers.items()):
            print(f"  {k}: {v}")


def cmd_search(args, key):
    search = SEARCH[args.platform]
    songs = search(key, args.keyword)
    if not songs:
        print("无结果")
        return
    for i, s in enumerate(songs, 1):
        print_song(i, s)
    print(f"\n共 {len(songs)} 条。复制歌曲 id 后用 download 子命令下载。")


def cmd_search_all(args, key):
    songs = search_all(key, args.keyword)
    if not songs:
        print("无结果")
        return
    for i, s in enumerate(songs, 1):
        label = PLATFORM_LABEL.get(s.get("platform", "?"), s.get("platform", "?"))
        print(f"  {i:>3}. [{label}] {s['name']} - {s['artist']}  《{s.get('album', '')}》  id={s['id']}")
    print(f"\n共 {len(songs)} 条（三平台合并）。复制 id 后用 download 子命令下载。")


def cmd_url(args, key):
    r = RESOLVE[args.platform](key, args.song_id, args.quality)
    if not r.get("url"):
        raise RuntimeError("未能解析出音频地址。可能该歌曲需要更高权限，或请尝试更低的音质档位。")
    print(f"音质: {r.get('level') or r.get('format')}  码率: {r.get('br')}")
    print(r["url"])


def cmd_download(args, key):
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    r = RESOLVE[args.platform](key, args.song_id, args.quality)
    url = r.get("url")
    if not url:
        if args.platform == "netease" and args.fallback:
            return download_netease_fallback(key, args.song_id, args.quality, out_dir, args.lyric, args.cover)
        raise RuntimeError("未能解析出音频地址。可能该歌曲需要更高权限，或请尝试更低的音质档位。")
    name = f"{sanitize(r.get('singer') or '')} - {sanitize(r.get('name') or args.song_id)}".strip(" -")
    ext = guess_ext(url, r.get("format"))
    if getattr(args, "ios", False):
        # 手机版：无歌单，用 歌手/专辑 文件夹充当专辑
        folder = out_dir
        singer = sanitize(r.get("singer") or "")
        album = sanitize(r.get("album") or "")
        if singer:
            folder = os.path.join(folder, singer)
        if album:
            folder = os.path.join(folder, album)
        os.makedirs(folder, exist_ok=True)
    else:
        folder = out_dir
    path = os.path.join(folder, f"{sanitize(name)}{ext}")
    print(f"下载 {args.platform} id={args.song_id}  音质={r.get('level') or r.get('format')}")
    if os.path.exists(path):
        print(f"  文件已存在，跳过: {path}")
        return path
    try:
        http_get(url, path)
    except Exception as e:
        raise
    print(f"  ✓ 已保存: {path}")
    if args.lyric or args.cover or getattr(args, "ios", False):
        # 仿 qmdec：歌词/封面内嵌进文件；未知字段留空则不覆盖原标签
        song = {"id": args.song_id, "name": r.get("name") or "",
                "artist": r.get("singer") or "", "album": r.get("album") or ""}
        flag = embed_song_data(key, path, args.platform, song,
                               lrc=r.get("lrc"), pic_url=r.get("picUrl") or r.get("cover"),
                               want_lyric=args.lyric or getattr(args, "ios", False), want_cover=args.cover,
                               sidecar_lrc=getattr(args, "ios", False))
        if flag:
            print(f"  ✓ {flag}")
    return path


def download_netease_fallback(key, sid, quality, out_dir, want_lyric, want_cover):
    """按 高->低 逐级尝试音质。"""
    idx = NETEASE_LEVELS.index(quality) if quality in NETEASE_LEVELS else NETEASE_LEVELS.index("lossless")
    for level in NETEASE_LEVELS[idx:]:
        try:
            r = resolve_netease(key, sid, level)
        except RuntimeError as e:
            print(f"  {level} 失败: {e}")
            continue
        if r.get("url"):
            print(f"  实际音质: {r.get('level')}")
            break
        print(f"  {level} 无地址，尝试更低音质...")
    else:
        raise RuntimeError("所有音质档位都无法解析，可能歌曲需更高权限。")
    name = f"netease_{sid}"
    ext = guess_ext(r["url"])
    path = os.path.join(out_dir, f"{name}{ext}")
    if os.path.exists(path):
        print(f"  文件已存在，跳过: {path}")
        return path
    http_get(r["url"], path)
    print(f"  ✓ 已保存: {path}")
    if want_lyric or want_cover:
        song = {"id": sid, "name": "", "artist": "", "album": ""}
        flag = embed_song_data(key, path, "netease", song,
                               pic_url=r.get("picUrl"), want_lyric=want_lyric, want_cover=want_cover)
        if flag:
            print(f"  ✓ {flag}")
    return path


def download_qq_song(key, mid, quality, out_dir, song, want_lyric=True, want_cover=True,
                     sidecar_lrc=False):
    """解析 QQ 音质（master->hires->flac->320k->128k 逐级降级）并下载+内嵌。

    song 需含 name/artist/album 作为命名与标签兜底；返回文件路径或 None。
    """
    idx = QQ_KUGOU_SIZES.index(quality) if quality in QQ_KUGOU_SIZES else QQ_KUGOU_SIZES.index("flac")
    r = None
    for size in QQ_KUGOU_SIZES[idx:]:
        try:
            r = resolve_qq(key, mid, size)
        except Exception as e:
            print(f"  {size} 解析失败: {e}")
            continue
        if r.get("url"):
            print(f"  音质: {size}")
            break
        print(f"  {size} 无地址，尝试更低音质...")
    if not r or not r.get("url"):
        print("  ✗ 无法解析，跳过（可能需要更高权限）")
        return None
    name = f"{sanitize(r.get('singer') or song['artist'])} - {sanitize(r.get('name') or song['name'])}".strip(" -")
    ext = guess_ext(r["url"], r.get("format"))
    if sidecar_lrc:
        folder = out_dir
        singer = sanitize(r.get("singer") or song.get("artist") or "")
        album = sanitize(r.get("album") or song.get("album") or "")
        if singer:
            folder = os.path.join(folder, singer)
        if album:
            folder = os.path.join(folder, album)
        os.makedirs(folder, exist_ok=True)
    else:
        folder = out_dir
    path = os.path.join(folder, f"{sanitize(name)}{ext}")
    if os.path.exists(path):
        print(f"  文件已存在，跳过: {path}")
        return path
    try:
        http_get(r["url"], path)
    except Exception as e:
        print(f"  ✗ 下载失败: {e}")
        return None
    print(f"  ✓ 已保存: {path}")
    if want_lyric or want_cover or sidecar_lrc:
        meta_song = {"id": mid, "name": r.get("name") or song.get("name") or "",
                     "artist": r.get("singer") or song.get("artist") or "",
                     "album": r.get("album") or song.get("album") or ""}
        flag = embed_song_data(key, path, "qq", meta_song, lrc=r.get("lrc"), pic_url=r.get("cover"),
                               want_lyric=want_lyric or sidecar_lrc, want_cover=want_cover,
                               sidecar_lrc=sidecar_lrc)
        if flag:
            print(f"  ✓ {flag}")
    return path


def lyric_netease(key, sid, audio_path):
    body, _ = api("/api/163_lyric", {"id": sid}, key)
    check_business(body)
    lrc = body.get("data", {}).get("lrc") or ""
    tlyric = body.get("data", {}).get("tlyric") or ""
    if not lrc and not tlyric:
        return
    base = os.path.splitext(audio_path)[0]
    save_text(base + ".lrc", lrc)
    if tlyric:
        save_text(base + ".tlyric.lrc", tlyric)
    print(f"  ✓ 歌词: {base}.lrc")


def save_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def cmd_find(args, key):
    search = SEARCH[args.platform]
    songs = search(key, args.keyword)
    if not songs:
        print("无结果")
        return
    for i, s in enumerate(songs, 1):
        print_song(i, s, show_id=(args.platform != "netease"))
    picks = pick_indices(len(songs))
    if not picks:
        print("未选择，退出")
        return
    ios_mode = getattr(args, "ios", False)
    for i in picks:
        s = songs[i]
        print(f"\n[{i + 1}/{len(picks)}] {s['name']} - {s['artist']}")
        out_dir = os.path.abspath(args.out)
        os.makedirs(out_dir, exist_ok=True)
        r = RESOLVE[args.platform](key, s["id"], args.quality)
        url = r.get("url")
        if not url and args.platform == "netease" and args.fallback:
            download_netease_fallback(key, s["id"], args.quality, out_dir, args.lyric, args.cover)
            continue
        if not url:
            print(f"  ✗ 无法解析，跳过")
            continue
        name = f"{sanitize(r.get('singer') or s['artist'])} - {sanitize(r.get('name') or s['name'])}".strip(" -")
        ext = guess_ext(url, r.get("format"))
        if ios_mode:
            # 手机版：无歌单，用 歌手/专辑 文件夹充当专辑
            folder = out_dir
            if s.get("artist"):
                folder = os.path.join(folder, sanitize(s["artist"]))
            if s.get("album"):
                folder = os.path.join(folder, sanitize(s["album"]))
            os.makedirs(folder, exist_ok=True)
        else:
            folder = out_dir
        path = os.path.join(folder, f"{sanitize(name)}{ext}")
        if os.path.exists(path):
            print(f"  文件已存在，跳过: {path}")
            continue
        try:
            http_get(url, path)
        except Exception as e:
            print(f"  ✗ 下载失败: {e}")
            continue
        print(f"  ✓ 已保存: {path}")
        if args.lyric or args.cover or ios_mode:
            song = {"id": s["id"], "name": s.get("name") or "", "artist": s.get("artist") or "",
                    "album": s.get("album") or ""}
            flag = embed_song_data(key, path, args.platform, song,
                                   lrc=r.get("lrc"), pic_url=r.get("picUrl") or r.get("cover"),
                                   want_lyric=args.lyric or ios_mode, want_cover=args.cover,
                                   sidecar_lrc=ios_mode)
            if flag:
                print(f"  ✓ {flag}")
    print("\n完成。")


def cmd_playlist(args, key):
    info, tracks = fetch_netease_playlist(key, args.playlist_id)
    print(f"歌单: {info.get('name')}  ({info.get('trackCount', len(tracks))} 首)")
    for i, s in enumerate(tracks, 1):
        print_song(i, s)
    picks = pick_indices(len(tracks))
    if not picks:
        print("未选择，退出")
        return
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    for i in picks:
        s = tracks[i]
        print(f"\n[{i + 1}/{len(picks)}] {s['name']} - {s['artist']}")
        download_netease_fallback(key, s["id"], args.quality, out_dir, args.lyric, args.cover)
    print("\n完成。")


def cmd_qqplaylist(args, key):
    """拉取 QQ 歌单并批量下载。歌单里直接取到 mid，不用一首一首搜。"""
    pid = parse_playlist_id(args.playlist_id)
    print(f"正在拉取 QQ 歌单 {pid} ...")
    info, tracks = fetch_qq_playlist(pid)
    if not tracks:
        raise RuntimeError("歌单为空或不是公开歌单。私有歌单请先在 QQ 音乐里设为「公开」。")
    tracks = normalize_qq_tracks(tracks)
    title = info.get("title") or "(无标题)"
    print(f"歌单: {title}  ({len(tracks)} 首)")
    for i, s in enumerate(tracks, 1):
        print_song(i, s)

    if getattr(args, "export", None):
        with open(args.export, "w", encoding="utf-8") as f:
            for s in tracks:
                f.write(f"{s['id']}\t{s['name']}\t{s['artist']}\t{s['album']}\n")
        print(f"✓ 歌单已导出: {args.export}（mid/歌名/歌手/专辑，制表符分隔）")
        if not args.all:
            print("仅导出。加 --all 可在导出后直接下载全部歌曲。")
            return

    picks = list(range(len(tracks))) if args.all else pick_indices(len(tracks))
    if not picks:
        print("未选择，退出")
        return
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    ios_mode = getattr(args, "ios", False)
    ok = 0
    for i in picks:
        s = tracks[i]
        print(f"\n[{i + 1}/{len(picks)}] {s['name']} - {s['artist']}")
        p = download_qq_song(key, s["id"], args.quality, out_dir, s,
                             want_lyric=args.lyric or ios_mode, want_cover=args.cover,
                             sidecar_lrc=ios_mode)
        if p:
            ok += 1
    print(f"\n完成：成功 {ok} / 选择 {len(picks)} 首。输出目录: {out_dir}")


# ---------------------------------------------------------------- 入口

def build_parser():
    p = argparse.ArgumentParser(prog="chksz_dl", description="ChKSz 音乐下载工具（网易云/QQ/酷狗）")
    sub = p.add_subparsers(dest="command", required=True)

    def add_key_common(sp, out_default="./music"):
        sp.add_argument("--key", help="ChKSz API Key（也可用环境变量 CHKSz_API_KEY 或 ~/.chksz_key）")
        sp.add_argument("-o", "--out", default=out_default, help=f"输出目录（默认 {out_default}）")
        sp.add_argument("-q", "--quality", help="音质：netease=standard/exhigh/lossless/hires/jyeffect/sky/jymaster；qq/kugou=128k/320k/flac/hires/master")

    def add_sub_key(sp):
        sp.add_argument("--key", help="ChKSz API Key（也可用环境变量 CHKSz_API_KEY 或 ~/.chksz_key）")

    c = sub.add_parser("check", help="验证 API Key")
    add_sub_key(c)
    c.add_argument("--dump", action="store_true", help="打印全部响应头（排查额度）")
    c.set_defaults(func=cmd_check)

    c = sub.add_parser("search", help="搜索歌曲")
    add_sub_key(c)
    c.add_argument("platform", choices=list(PLATFORM_ALIASES), help="netease/qq/kugou")
    c.add_argument("keyword", help="关键词")
    c.set_defaults(func=cmd_search)

    c = sub.add_parser("search-all", help="聚合搜索三平台")
    add_sub_key(c)
    c.add_argument("keyword", help="关键词")
    c.set_defaults(func=cmd_search_all)

    c = sub.add_parser("url", help="打印音频直链")
    add_sub_key(c)
    c.add_argument("platform", choices=list(PLATFORM_ALIASES), help="netease/qq/kugou")
    c.add_argument("song_id", help="歌曲 id（netease 为数字 id；qq 为 mid；kugou 为歌曲 id）")
    c.add_argument("-q", "--quality", default=None)
    c.set_defaults(func=cmd_url)

    c = sub.add_parser("download", help="按歌曲 id 下载")
    add_key_common(c)
    c.add_argument("platform", choices=list(PLATFORM_ALIASES), help="netease/qq/kugou")
    c.add_argument("song_id", help="歌曲 id")
    c.add_argument("--lyric", action="store_true", help="内嵌歌词到文件")
    c.add_argument("--cover", action="store_true", help="内嵌封面到文件")
    c.add_argument("--ios", action="store_true", help="手机版：按歌手/专辑分文件夹，并写旁车 .lrc 供 iOS 显示歌词")
    c.add_argument("--no-fallback", action="store_false", dest="fallback", default=True,
                   help="netease 音质解析失败时不做降级")
    c.set_defaults(func=cmd_download)

    c = sub.add_parser("find", help="搜索后交互选择下载")
    c.add_argument("platform", choices=list(PLATFORM_ALIASES))
    c.add_argument("keyword")
    add_key_common(c)
    c.add_argument("--lyric", action="store_true", help="内嵌歌词到文件")
    c.add_argument("--cover", action="store_true", help="内嵌封面到文件")
    c.add_argument("--ios", action="store_true", help="手机版：按歌手/专辑分文件夹，并写旁车 .lrc")
    c.add_argument("--no-fallback", action="store_false", dest="fallback", default=True)
    c.set_defaults(func=cmd_find)

    c = sub.add_parser("playlist", help="拉取网易云歌单并下载")
    c.add_argument("playlist_id", help="网易云歌单 id")
    add_key_common(c)
    c.add_argument("--lyric", action="store_true")
    c.add_argument("--cover", action="store_true")
    c.set_defaults(func=cmd_playlist)

    c = sub.add_parser("qqplaylist", help="拉取 QQ 音乐歌单并批量下载")
    c.add_argument("playlist_id", help="QQ 歌单 ID 或完整链接，如 9080103532 或 https://y.qq.com/n/ryqq/playlist/9080103532")
    add_key_common(c)
    c.add_argument("--all", action="store_true", help="直接下载全部歌曲（默认交互选择序号）")
    c.add_argument("--export", metavar="FILE", help="导出歌单歌曲列表到文件（mid/歌名/歌手/专辑）；不配合 --all 时只导出不下载")
    c.add_argument("--lyric", action="store_true")
    c.add_argument("--cover", action="store_true")
    c.add_argument("--ios", action="store_true", help="手机版：按歌手/专辑分文件夹，并写旁车 .lrc")
    c.set_defaults(func=cmd_qqplaylist)

    return p


def default_quality(platform):
    return "lossless" if platform == "netease" else "flac"


def main():
    args = build_parser().parse_args()
    args.platform = PLATFORM_ALIASES.get(getattr(args, "platform", None), getattr(args, "platform", None))
    if not getattr(args, "quality", None):
        args.quality = default_quality(args.platform)
    key = resolve_key(getattr(args, "key", None))
    if not key:
        try:
            key = prompt_key()
        except KeyboardInterrupt:
            print("\n已取消")
            sys.exit(1)
    try:
        args.func(args, key)
    except RuntimeError as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
