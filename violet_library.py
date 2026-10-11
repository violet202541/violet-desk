"""书信匣：扫描本地曲库，读取标签、封面与歌词。从不改写音乐文件；只有你亲手退回的歌会被移进回收站。"""
import hashlib
import json
import os
from pathlib import Path
import threading

from violet_core import DATA_DIR

AUDIO_EXTS = {'.mp3', '.flac', '.m4a', '.aac', '.ogg', '.opus', '.wav'}
AUDIO_MIME = {'.mp3': 'audio/mpeg', '.flac': 'audio/flac', '.m4a': 'audio/mp4', '.aac': 'audio/aac',
              '.ogg': 'audio/ogg', '.opus': 'audio/ogg', '.wav': 'audio/wav'}
CACHE_FILE = DATA_DIR / 'library-cache.json'
CACHE_VERSION = 2
FOLDER_COVERS = ('cover.jpg', 'cover.png', 'folder.jpg', 'front.jpg')
# Files the downloader writes next to a song, named after it; they leave together with it.
SIDECARS = ('.lrc', '.tlyric.lrc', '.jpg', '.jpeg', '.png', '.webp')


def track_id(path):
    return hashlib.sha1(os.path.normcase(os.path.abspath(path)).encode('utf-8')).hexdigest()[:16]


def _first(tags, *names):
    for name in names:
        value = tags.get(name) if tags is not None else None
        if value is None:
            continue
        if isinstance(value, list):
            value = value[0] if value else None
        if hasattr(value, 'text'):
            value = value.text[0] if value.text else None
        if value:
            return str(value).strip()
    return ''


def read_tags(path):
    """Title/artist/album/duration and whether cover/lyrics exist, without loading images."""
    import mutagen
    info = {'title': '', 'artist': '', 'album': '', 'duration': 0, 'has_cover': False, 'has_lyrics': False}
    try:
        audio = mutagen.File(path)
    except Exception:
        audio = None
    if audio is not None:
        if getattr(audio, 'info', None) and getattr(audio.info, 'length', None):
            info['duration'] = int(audio.info.length * 1000)
        tags = audio.tags
        cls = type(audio).__name__
        if cls in ('MP3', 'EasyMP3') and tags is not None:
            info['title'] = _first(tags, 'TIT2')
            info['artist'] = _first(tags, 'TPE1')
            info['album'] = _first(tags, 'TALB')
            info['has_cover'] = any(k.startswith('APIC') for k in tags.keys())
            info['has_lyrics'] = any(k.startswith('USLT') for k in tags.keys())
        elif cls == 'MP4' and tags is not None:
            info['title'] = _first(tags, '\xa9nam')
            info['artist'] = _first(tags, '\xa9ART')
            info['album'] = _first(tags, '\xa9alb')
            info['has_cover'] = 'covr' in tags
            info['has_lyrics'] = '\xa9lyr' in tags
        elif tags is not None:
            info['title'] = _first(tags, 'title', 'TITLE')
            info['artist'] = _first(tags, 'artist', 'ARTIST')
            info['album'] = _first(tags, 'album', 'ALBUM')
            info['has_lyrics'] = bool(_first(tags, 'lyrics', 'LYRICS', 'unsyncedlyrics', 'UNSYNCEDLYRICS'))
            info['has_cover'] = bool(getattr(audio, 'pictures', None)) or 'metadata_block_picture' in tags
    stem = Path(path).stem
    if not info['title']:
        # Downloaded files are named "artist - title".
        if ' - ' in stem:
            artist, title = stem.split(' - ', 1)
            info['title'], info['artist'] = title.strip(), info['artist'] or artist.strip()
        else:
            info['title'] = stem
    if os.path.isfile(os.path.splitext(path)[0] + '.lrc'):
        info['has_lyrics'] = True
    if not info['has_cover']:
        info['has_cover'] = _folder_cover(path) is not None
    return info


def sidecars(path):
    base = os.path.splitext(path)[0]
    return [base + s for s in SIDECARS if os.path.isfile(base + s)]


def recycle(paths):
    """Move files to the Windows Recycle Bin, so a song sent back by mistake can still be fished out."""
    paths = [os.path.abspath(p) for p in paths if os.path.exists(p)]
    if not paths:
        return
    if os.name != 'nt':
        raise OSError('只有在 Windows 上才能把歌移进回收站')
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [('hwnd', wintypes.HWND), ('wFunc', wintypes.UINT), ('pFrom', wintypes.LPCWSTR),
                    ('pTo', wintypes.LPCWSTR), ('fFlags', ctypes.c_uint16), ('fAnyOperationsAborted', wintypes.BOOL),
                    ('hNameMappings', ctypes.c_void_p), ('lpszProgressTitle', wintypes.LPCWSTR)]

    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 3, 0x4, 0x10, 0x40, 0x400
    op = SHFILEOPSTRUCTW(wFunc=FO_DELETE, pFrom='\0'.join(paths) + '\0',
                         fFlags=FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI)
    code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if code or op.fAnyOperationsAborted or any(os.path.exists(p) for p in paths):
        raise OSError(f'没能移进回收站（文件可能正被别的程序占用，代码 {code}）')


def _folder_cover(path):
    folder = os.path.dirname(path)
    for name in FOLDER_COVERS:
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def read_cover(path):
    """Embedded front cover (or folder image) as (bytes, mime), or None."""
    import mutagen
    try:
        audio = mutagen.File(path)
    except Exception:
        audio = None
    if audio is not None and audio.tags is not None:
        cls = type(audio).__name__
        try:
            if cls == 'MP3':
                pics = [audio.tags[k] for k in audio.tags.keys() if k.startswith('APIC')]
                if pics:
                    pic = next((p for p in pics if p.type == 3), pics[0])
                    return pic.data, pic.mime or 'image/jpeg'
            elif cls == 'MP4':
                covers = audio.tags.get('covr')
                if covers:
                    cover = covers[0]
                    mime = 'image/png' if getattr(cover, 'imageformat', 0) == 14 else 'image/jpeg'
                    return bytes(cover), mime
            else:
                pictures = getattr(audio, 'pictures', None) or []
                if pictures:
                    pic = next((p for p in pictures if p.type == 3), pictures[0])
                    return pic.data, pic.mime or 'image/jpeg'
        except Exception:
            pass
    folder_cover = _folder_cover(path)
    if folder_cover:
        mime = 'image/png' if folder_cover.lower().endswith('.png') else 'image/jpeg'
        return Path(folder_cover).read_bytes(), mime
    return None


def read_lyrics(path):
    """Sidecar .lrc first, then embedded lyrics. Returns text or ''."""
    sidecar = os.path.splitext(path)[0] + '.lrc'
    if os.path.isfile(sidecar):
        raw = Path(sidecar).read_bytes()
        for encoding in ('utf-8-sig', 'gb18030'):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
    import mutagen
    try:
        audio = mutagen.File(path)
    except Exception:
        return ''
    if audio is None or audio.tags is None:
        return ''
    cls = type(audio).__name__
    try:
        if cls == 'MP3':
            for k in audio.tags.keys():
                if k.startswith('USLT'):
                    return audio.tags[k].text
        elif cls == 'MP4':
            return (audio.tags.get('\xa9lyr') or [''])[0]
        else:
            return _first(audio.tags, 'lyrics', 'LYRICS', 'unsyncedlyrics', 'UNSYNCEDLYRICS')
    except Exception:
        return ''
    return ''


class Library:
    """Index of audio files below the configured roots, cached by size and mtime."""

    def __init__(self, cache_file=None):
        self.cache_file = Path(cache_file or CACHE_FILE)
        self._lock = threading.Lock()
        self._scan_lock = threading.Lock()
        self.tracks = {}
        self.roots = []
        self._cache = {}
        try:
            data = json.loads(self.cache_file.read_text(encoding='utf-8'))
            if data.get('version') == CACHE_VERSION:
                self._cache = data.get('entries', {})
        except (OSError, ValueError, AttributeError):
            pass

    def scan(self, roots):
        with self._scan_lock:
            found, cache = {}, {}
            for root in roots:
                if not os.path.isdir(root):
                    continue
                for folder, dirs, files in os.walk(root):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for name in files:
                        ext = os.path.splitext(name)[1].lower()
                        if ext not in AUDIO_EXTS or name.startswith('.'):
                            continue
                        path = os.path.join(folder, name)
                        try:
                            stat = os.stat(path)
                        except OSError:
                            continue
                        stamp = [stat.st_size, int(stat.st_mtime)]
                        cached = self._cache.get(path)
                        lrc = os.path.isfile(os.path.splitext(path)[0] + '.lrc')
                        if cached and cached.get('stamp') == stamp and cached.get('lrc') == lrc:
                            info = cached['info']
                        else:
                            info = read_tags(path)
                        cache[path] = {'stamp': stamp, 'lrc': lrc, 'info': info}
                        tid = track_id(path)
                        found[tid] = dict(info, id=tid, path=path, ext=ext[1:], size=stat.st_size,
                                          mtime=int(stat.st_mtime), folder=os.path.relpath(folder, root),
                                          root=root)
            with self._lock:
                self.tracks, self.roots, self._cache = found, list(roots), cache
            try:
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.cache_file.with_name(self.cache_file.name + '.tmp')
                temporary.write_text(json.dumps({'version': CACHE_VERSION, 'entries': cache}, ensure_ascii=False),
                                     encoding='utf-8')
                temporary.replace(self.cache_file)
            except OSError:
                pass
            return self.list()

    def list(self):
        with self._lock:
            tracks = list(self.tracks.values())
        tracks.sort(key=lambda t: (-t['mtime'], t['artist'].lower(), t['title'].lower()))
        return [{k: v for k, v in t.items() if k not in ('root',)} for t in tracks]

    def forget(self, ids):
        """Drop songs that were sent back from the index (and its cache), without rescanning."""
        with self._lock:
            for tid in ids:
                track = self.tracks.pop(tid, None)
                if track:
                    self._cache.pop(track['path'], None)

    def path_for(self, tid):
        """Only indexed files are served; arbitrary paths are never accepted."""
        with self._lock:
            track = self.tracks.get(tid)
        if track and os.path.isfile(track['path']):
            return track['path']
        return None
