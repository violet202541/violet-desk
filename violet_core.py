"""Violet 的界面无关核心：偏好、Key、下载队列与持久化寄信记录。

下载线程只读取入队时的设置与 Key 快照；之后修改设置不影响已入队任务。
所有状态变化通过 EventBus 推送给界面（本地 HTTP 服务以 SSE 转发）。
"""
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
import json
import os
from pathlib import Path
import queue
import re
import sys
import threading
import time
import uuid

from chksz_dl import (KEY_FILE, NETEASE_LEVELS, QQ_KUGOU_SIZES, RESOLVE, ApiError, DownloadCancelled,
                      api_session, check_cancel, embed_song_data, guess_ext, parse_quota, sanitize,
                      stream_download)

APP_NAME = 'Violet'
APP_VERSION = '5.8'
MAX_CONCURRENT_DOWNLOADS = 4
HISTORY_LIMIT = 500

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent


def default_data_dir():
    """Personal data lives outside the program folder, so the bat and the exe share it and rebuilds never wipe it."""
    override = os.environ.get('VIOLET_DATA_DIR', '').strip()
    if override:
        return Path(override).expanduser().resolve()
    if os.name == 'nt' and os.environ.get('APPDATA'):
        return Path(os.environ['APPDATA']) / 'Violet'
    return Path.home() / '.violet'


DATA_DIR = default_data_dir()
SETTINGS_FILE = DATA_DIR / 'settings.json'
HISTORY_FILE = DATA_DIR / 'history.json'
# Files written next to the program before v5, and their new names in DATA_DIR.
LEGACY_FILES = {'.violet_settings.json': 'settings.json', '.violet_history.json': 'history.json',
                '.violet_letters.json': 'letters.json', '.violet_plays.json': 'plays.json',
                '.violet_library.json': 'library-cache.json'}
MIGRATION_MARK = 'migrated.json'

PLATFORM_LABEL = {'netease': '网易云', 'qq': 'QQ音乐', 'kugou': '酷狗'}
QUALITY_OPTIONS = {'netease': NETEASE_LEVELS, 'qq': QQ_KUGOU_SIZES, 'kugou': QQ_KUGOU_SIZES}
QUALITY_LABELS = {'jymaster': '超清母带', 'sky': '沉浸环绕', 'jyeffect': '高清环绕', 'hires': 'Hi-Res',
                  'lossless': '无损 FLAC', 'exhigh': '极高 320K', 'standard': '标准',
                  'master': '臻品母带', 'flac': '无损 FLAC', '320k': '高品 320K', '128k': '标准 128K'}
THEMES = ('auto', 'light', 'dark')
PORTRAITS = ('art', 'custom', 'off')
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')
TERMINAL_STATES = {'done', 'skipped', 'failed', 'cancelled'}
# Errors that mean "stop asking this service for now"; 401/402/429 affect every platform.
STOP_ALL = {401, 402, 429}
STOP_PLATFORM = {403, 503}
KEY_PATTERN = re.compile(r'chksz_[A-Za-z0-9_-]+')


def safe_error(error):
    return KEY_PATTERN.sub('[KEY]', str(error))[:300]


def legacy_sources():
    """Folders that may hold pre-v5 data: the program folder, and for a build inside the project, the project."""
    sources = [APP_DIR]
    project = APP_DIR.parent.parent
    if getattr(sys, 'frozen', False) and (project / 'violet_app.py').is_file():
        sources.insert(0, project)
    return sources


def migrate_legacy(data_dir=None, sources=None):
    """Copy (never move) pre-v5 data into the data folder once. Returns the folder migrated from, or None."""
    data_dir = Path(data_dir or DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    mark = data_dir / MIGRATION_MARK
    if mark.exists():
        return None
    source = next((folder for folder in (sources or legacy_sources())
                   if any((Path(folder) / name).is_file() for name in LEGACY_FILES)), None)
    copied = []
    if source:
        for old, new in LEGACY_FILES.items():
            origin, target = Path(source) / old, data_dir / new
            if not origin.is_file() or target.exists():
                continue
            raw = origin.read_bytes()
            if new == 'settings.json':
                raw = _absolute_settings(raw, Path(source))
            target.write_bytes(raw)
            copied.append(new)
    _write_json(mark, {'from': str(source) if source else '', 'files': copied, 'time': time.time()})
    return source


def _absolute_settings(raw, base):
    """Relative folders used to mean "next to the program"; pin them so moving data keeps them pointing home."""
    try:
        data = json.loads(raw.decode('utf-8'))
    except ValueError:
        return raw
    if not isinstance(data, dict):
        return raw

    def pin(path):
        path = os.path.expanduser(str(path).strip())
        return path if os.path.isabs(path) else os.path.normpath(os.path.join(base, path))

    if isinstance(data.get('out_dir'), str) and data['out_dir'].strip():
        data['out_dir'] = pin(data['out_dir'])
    if isinstance(data.get('library_dirs'), list):
        data['library_dirs'] = [pin(d) for d in data['library_dirs'] if isinstance(d, str) and d.strip()]
    return json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')


def installed():
    """An installed copy (the setup leaves its uninstaller beside the exe) may sit in a read-only Program Files."""
    return getattr(sys, 'frozen', False) and (APP_DIR / 'unins000.exe').is_file()


def resolve_dir(path):
    """Relative folders are anchored to the app folder, not the launch directory.
    An installed copy keeps songs in the user's Music folder instead, so uninstalling never takes them."""
    path = os.path.expanduser(str(path or '').strip() or './music')
    if not os.path.isabs(path):
        if installed():
            home = os.path.join(os.path.expanduser('~'), 'Music', 'Violet')
            path = home if os.path.normpath(path) == 'music' else os.path.join(home, path)
        else:
            path = os.path.join(APP_DIR, path)
    return os.path.normpath(path)


# 文具匣：一封信用的信纸、格线、抬头、字、墨、火漆、邮票、信封与落款。只收认得的键，值都是短字符串。
STATIONERY_KEYS = ('paper', 'ruling', 'letterhead', 'font', 'ink', 'seal_color', 'seal_motif', 'seal_initials',
                   'stamp', 'stamp_tone', 'envelope', 'signoff')
DEFAULT_STATIONERY = {'paper': 'parchment', 'ruling': 'lines', 'letterhead': 'violets', 'font': 'wenkai',
                      'ink': 'violet', 'seal_color': 'violet', 'seal_motif': 'monogram', 'seal_initials': '',
                      'stamp': 'harbor', 'stamp_tone': 'color', 'envelope': 'western', 'signoff': ''}


def clean_stationery(data, base=None):
    """Merge the known stationery fields of `data` over `base`; anything unknown or malformed is dropped."""
    out = dict(base or {})
    if not isinstance(data, dict):
        return out
    for key in STATIONERY_KEYS:
        value = data.get(key)
        if not isinstance(value, str):
            continue
        value = ' '.join(value.split())
        if key == 'seal_initials':
            out[key] = value[:3]
        elif key == 'signoff':
            out[key] = value[:16]
        elif re.fullmatch(r'[\w:.\-]{0,64}', value):
            out[key] = value
    return out


@dataclass
class Settings:
    out_dir: str = './music'
    qualities: dict = field(default_factory=lambda: {'netease': 'lossless', 'qq': 'flac', 'kugou': 'flac'})
    lyric: bool = True
    cover: bool = True
    subfolders: bool = False
    ios: bool = False
    theme: str = 'auto'
    sound: bool = False
    library_dirs: list = field(default_factory=list)
    portrait: str = 'art'
    portrait_path: str = ''
    intro: bool = True
    tray: bool = True
    ambient: bool = True
    backup_dir: str = ''
    # 每日来信的新歌从哪儿挑（见 violet_letters.CHART_CATALOG）。
    letter_charts: list = field(default_factory=lambda: ['netease:19723756', 'netease:3779629', 'qq:62', 'qq:27', 'qq:26'])
    letter_taste: bool = True
    letter_playlists: list = field(default_factory=list)
    letter_count: int = 3
    nickname: str = ''  # how Violet addresses you in her letters
    signoff: str = ''  # how you sign your replies
    # 桌面歌词：一条浮在最上层的纸笺；锁定后纸笺隐去，只留描边的字，鼠标可以穿过去。
    desktop_lyrics: bool = False
    lyrics_locked: bool = False
    lyrics_size: int = 32
    lyrics_pos: list = field(default_factory=list)
    stationery: dict = field(default_factory=lambda: dict(DEFAULT_STATIONERY))
    photo_stamps: list = field(default_factory=list)  # photos (in the photo folder) cut into stamps

    @classmethod
    def from_dict(cls, data, base=None):
        settings = replace(base) if base else cls()
        settings.qualities = dict(settings.qualities)
        settings.library_dirs = list(settings.library_dirs)
        settings.letter_charts = list(settings.letter_charts)
        settings.letter_playlists = list(settings.letter_playlists)
        settings.stationery = clean_stationery(settings.stationery, DEFAULT_STATIONERY)
        settings.photo_stamps = list(settings.photo_stamps)
        if not isinstance(data, dict):
            return settings
        if isinstance(data.get('out_dir'), str) and data['out_dir'].strip():
            settings.out_dir = data['out_dir'].strip()
        if data.get('theme') in THEMES:
            settings.theme = data['theme']
        if data.get('portrait') in PORTRAITS:
            settings.portrait = data['portrait']
        elif data.get('portrait') == 'ink':  # the v4 line drawing was replaced by the watercolour
            settings.portrait = 'art'
        for name, limit in (('nickname', 12), ('signoff', 16)):
            if isinstance(data.get(name), str):
                setattr(settings, name, ' '.join(data[name].split())[:limit])
        if isinstance(data.get('backup_dir'), str):
            settings.backup_dir = data['backup_dir'].strip()
        if isinstance(data.get('portrait_path'), str):
            path = data['portrait_path'].strip()
            if not path or path.lower().endswith(IMAGE_EXTS):
                settings.portrait_path = path
        if isinstance(data.get('letter_charts'), list):
            settings.letter_charts = [c for c in dict.fromkeys(data['letter_charts']) if isinstance(c, str) and
                                      re.fullmatch(r'(qq|netease):\d+', c)][:20]
        if isinstance(data.get('letter_playlists'), list):
            from violet_letters import parse_playlist_link
            playlists = [p.strip()[:300] for p in data['letter_playlists'] if isinstance(p, str) and p.strip()][:10]
            for link in playlists:
                parse_playlist_link(link)  # a link that cannot be read is refused right away, not discovered tomorrow
            settings.letter_playlists = list(dict.fromkeys(playlists))
        count = data.get('letter_count')
        if isinstance(count, int) and not isinstance(count, bool) and 1 <= count <= 5:
            settings.letter_count = count
        if isinstance(data.get('stationery'), dict):
            settings.stationery = clean_stationery(data['stationery'], settings.stationery)
        if isinstance(data.get('photo_stamps'), list):
            settings.photo_stamps = [p for p in dict.fromkeys(data['photo_stamps'])
                                     if isinstance(p, str) and re.fullmatch(r'[0-9a-f]{16}\.(jpg|png|webp|gif)', p)][:24]
        size = data.get('lyrics_size')
        if isinstance(size, int) and not isinstance(size, bool) and 20 <= size <= 56:
            settings.lyrics_size = size
        pos = data.get('lyrics_pos')
        if isinstance(pos, list) and (not pos or (len(pos) == 2 and all(isinstance(v, int) for v in pos))):
            settings.lyrics_pos = list(pos)
        for name in ('lyric', 'cover', 'subfolders', 'ios', 'sound', 'intro', 'tray', 'ambient', 'letter_taste',
                     'desktop_lyrics', 'lyrics_locked'):
            if isinstance(data.get(name), bool):
                setattr(settings, name, data[name])
        qualities = data.get('qualities')
        if isinstance(qualities, dict):
            for platform, options in QUALITY_OPTIONS.items():
                if qualities.get(platform) in options:
                    settings.qualities[platform] = qualities[platform]
        dirs = data.get('library_dirs')
        if isinstance(dirs, list):
            settings.library_dirs = [d.strip() for d in dirs if isinstance(d, str) and d.strip()][:20]
        return settings

    @classmethod
    def load(cls):
        try:
            return cls.from_dict(json.loads(SETTINGS_FILE.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            return cls()

    def save(self):
        # Credentials never enter the preferences file.
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _write_json(SETTINGS_FILE, asdict(self))

    def to_dict(self):
        data = asdict(self)
        data['out_dir_abs'] = resolve_dir(self.out_dir)
        data['data_dir'] = str(SETTINGS_FILE.parent)
        return data

    def letter_sources(self):
        return {'charts': self.letter_charts, 'taste': self.letter_taste, 'playlists': self.letter_playlists,
                'count': self.letter_count}

    def library_roots(self):
        roots = [resolve_dir(self.out_dir)] + [resolve_dir(d) for d in self.library_dirs]
        seen, unique = set(), []
        for root in roots:
            key = os.path.normcase(root)
            if key not in seen:
                seen.add(key)
                unique.append(root)
        return unique


def _write_json(path, data):
    """Write to a temporary file, flush it to disk, then swap it in, so a crash never leaves half a file."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with open(temporary, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))
        f.flush()
        os.fsync(f.fileno())
    temporary.replace(path)


class KeyStore:
    """The API key lives in memory; remembering writes the CLI's ~/.chksz_key."""

    def __init__(self, key_file=None):
        self.key_file = Path(key_file or KEY_FILE)
        self.key = None
        self.source = None
        env = os.environ.get('CHKSZ_API_KEY', '').strip()
        if env:
            self.key, self.source = env, 'env'
            return
        for path in (self.key_file, APP_DIR / '.chksz_key'):
            try:
                for line in Path(path).read_text(encoding='utf-8').splitlines():
                    if line.strip():
                        self.key, self.source = line.strip(), 'file'
                        return
            except OSError:
                continue

    def set(self, key, remember):
        key = (key or '').strip()
        if not KEY_PATTERN.fullmatch(key):
            raise ValueError('Key 应以 chksz_ 开头，只包含字母、数字、下划线和短横线')
        self.key = key
        if remember:
            self.key_file.write_text(key + '\n', encoding='utf-8')
            self.source = 'file'
        else:
            self.source = 'session'

    def forget(self):
        """Forget the key for this session and remove the remembered copy."""
        try:
            stored = self.key_file.read_text(encoding='utf-8').strip()
            if stored == self.key or self.source == 'file':
                self.key_file.unlink()
        except OSError:
            pass
        self.key, self.source = None, None

    def status(self):
        masked = ''
        if self.key:
            masked = self.key[:6] + '…' + self.key[-4:]
        return {'has_key': bool(self.key), 'masked': masked, 'source': self.source,
                'remembered': self.source == 'file'}


class EventBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers = set()

    def subscribe(self):
        q = queue.Queue(maxsize=2000)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, kind, data):
        message = {'type': kind, 'data': data}
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(message)
            except queue.Full:
                pass


def song_summary(song):
    keep = ('platform', 'id', 'name', 'artist', 'album', 'picUrl', 'cover', 'album_mid', 'duration')
    return {k: song.get(k) for k in keep if song.get(k) not in (None, '')}


@dataclass
class DownloadJob:
    song: dict
    settings: Settings
    key: str = field(repr=False)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: str = 'queued'
    detail: str = '等待空闲的寄送位'
    pct: float = 0
    done_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0
    level: str = ''
    path: str = ''
    flags: str = ''
    created: float = field(default_factory=time.time)
    finished: float = 0
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def identity(self):
        return (self.song['platform'], str(self.song['id']), self.settings.out_dir,
                self.settings.subfolders, self.settings.ios)

    def to_dict(self):
        return {'id': self.id, 'song': song_summary(self.song), 'state': self.state, 'detail': self.detail,
                'pct': round(self.pct, 1), 'done_bytes': self.done_bytes, 'total_bytes': self.total_bytes,
                'speed': round(self.speed), 'level': self.level, 'path': self.path, 'flags': self.flags,
                'created': self.created, 'finished': self.finished}

    def history_record(self):
        record = self.to_dict()
        record['settings'] = asdict(self.settings)
        return record


class History:
    """Finished letters, newest first, kept across sessions (no keys stored)."""

    def __init__(self, path=None):
        self.path = Path(path or HISTORY_FILE)
        self.save_error = ''
        self._lock = threading.Lock()
        self.records = []
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(data, list):
                self.records = [r for r in data if isinstance(r, dict) and r.get('id')][:HISTORY_LIMIT]
        except (OSError, ValueError):
            pass

    def add(self, record):
        with self._lock:
            self.records = [r for r in self.records if r['id'] != record['id']]
            self.records.insert(0, record)
            del self.records[HISTORY_LIMIT:]
            self._save()

    def remove(self, ids):
        ids = set(ids)
        with self._lock:
            self.records = [r for r in self.records if r['id'] not in ids]
            self._save()

    def clear(self):
        with self._lock:
            self.records = []
            self._save()

    def forget_paths(self, paths):
        """Records of files that were sent back, so the same song can be fetched again."""
        gone = {os.path.normcase(os.path.abspath(p)) for p in paths}
        with self._lock:
            kept = [r for r in self.records if not r.get('path') or os.path.normcase(os.path.abspath(r['path'])) not in gone]
            if len(kept) != len(self.records):
                self.records = kept
                self._save()

    def get(self, record_id):
        with self._lock:
            return next((r for r in self.records if r['id'] == record_id), None)

    def snapshot(self):
        with self._lock:
            return [dict(r) for r in self.records]

    def _save(self):
        # A download must not fail because the record could not be written; remember why instead.
        try:
            _write_json(self.path, self.records)
            self.save_error = ''
        except OSError as error:
            self.save_error = f'寄信记录没能保存：{error.strerror or error}'


class DownloadManager:
    def __init__(self, bus, history, max_workers=MAX_CONCURRENT_DOWNLOADS):
        self.bus = bus
        self.history = history
        self.max_workers = max_workers
        self.jobs = []
        self.running = 0
        self.closing = False
        self._lock = threading.RLock()
        self.quota = {}

    # ------------------------------------------------------------ observers

    def observe_quota(self, headers):
        quota = parse_quota(headers)
        if quota:
            self.quota = {'free': quota.get('X-Quota-Free-Remaining'),
                          'paid': quota.get('X-Quota-Paid-Remaining'),
                          'updated': time.time()}
            self.bus.publish('quota', self.quota)

    def _emit(self, job):
        self.bus.publish('job', job.to_dict())

    # ------------------------------------------------------------ queue API

    def active(self):
        with self._lock:
            return [job for job in self.jobs if job.state not in TERMINAL_STATES]

    def snapshot(self):
        with self._lock:
            return [job.to_dict() for job in self.jobs]

    def enqueue(self, songs, settings, key):
        """Queue songs with a frozen settings/key snapshot. Returns (added, duplicates)."""
        if not key:
            raise PermissionError('需要先配置 API Key')
        settings = replace(settings, out_dir=resolve_dir(settings.out_dir),
                           qualities=dict(settings.qualities), library_dirs=list(settings.library_dirs))
        os.makedirs(settings.out_dir, exist_ok=True)
        added, duplicates = [], 0
        with self._lock:
            pending = {job.identity for job in self.jobs if job.state not in TERMINAL_STATES}
            for song in songs:
                if not isinstance(song, dict) or song.get('platform') not in QUALITY_OPTIONS or not song.get('id'):
                    continue
                job = DownloadJob(dict(song, id=str(song['id'])), settings, key)
                if job.identity in pending:
                    duplicates += 1
                    continue
                pending.add(job.identity)
                added.append(job)
            self.jobs.extend(added)
        for job in added:
            self._emit(job)
        self._pump()
        return added, duplicates

    def cancel(self, job_id=None):
        changed = []
        with self._lock:
            for job in self.jobs:
                if job_id and job.id != job_id:
                    continue
                if job.state in TERMINAL_STATES or job.state in ('finishing', 'cancelling'):
                    continue
                job.cancel.set()
                if job.state == 'queued':
                    job.state, job.detail = 'cancelled', '已从等待队列撤回'
                    job.finished = time.time()
                    self.history.add(job.history_record())
                else:
                    job.state, job.detail = 'cancelling', '等待当前网络请求返回'
                changed.append(job)
        for job in changed:
            self._emit(job)
        return len(changed)

    def retry(self, key, job_id=None):
        """Retry failed/cancelled jobs from this session with their original settings."""
        if not key:
            raise PermissionError('需要先配置 API Key')
        retried = []
        with self._lock:
            pending = {job.identity for job in self.jobs if job.state not in TERMINAL_STATES}
            for job in self.jobs:
                if job_id and job.id != job_id:
                    continue
                if job.state not in ('failed', 'cancelled') or job.identity in pending:
                    continue
                pending.add(job.identity)
                job.key, job.cancel = key, threading.Event()
                job.state, job.detail = 'queued', '等待重新寄出'
                job.pct, job.done_bytes, job.total_bytes, job.speed, job.path, job.finished = 0, 0, 0, 0, '', 0
                retried.append(job)
        if retried:
            self.history.remove([job.id for job in retried])
        for job in retried:
            self._emit(job)
        self._pump()
        return len(retried)

    def retry_record(self, record_id, key):
        """Re-send a letter recorded in a previous session with its stored settings."""
        record = self.history.get(record_id)
        if not record:
            raise LookupError('记录不存在')
        with self._lock:
            live = next((job for job in self.jobs if job.id == record_id), None)
        if live:
            return self.retry(key, record_id)
        settings = Settings.from_dict(record.get('settings') or {})
        added, _ = self.enqueue([record['song']], settings, key)
        if added:
            self.history.remove([record_id])
        return len(added)

    def clear_finished(self):
        with self._lock:
            before = len(self.jobs)
            self.jobs = [job for job in self.jobs if job.state not in TERMINAL_STATES]
            removed = before - len(self.jobs)
        self.bus.publish('jobs', self.snapshot())
        return removed

    def shutdown(self):
        self.closing = True
        with self._lock:
            for job in self.jobs:
                job.cancel.set()

    # ------------------------------------------------------------ workers

    def _pump(self):
        start = []
        with self._lock:
            if self.closing:
                return
            for job in self.jobs:
                if self.running >= self.max_workers:
                    break
                if job.state == 'queued':
                    self.running += 1
                    job.state, job.detail = 'resolving', '解析下载地址'
                    start.append(job)
        for job in start:
            self._emit(job)
            threading.Thread(target=self._run, args=(job,), name=f'violet-dl-{job.id}', daemon=True).start()
        self.bus.publish('summary', self.summary())

    def summary(self):
        with self._lock:
            counts = Counter(job.state for job in self.jobs)
        return {'counts': dict(counts), 'active': sum(c for s, c in counts.items() if s not in TERMINAL_STATES)}

    def _update(self, job, **changes):
        with self._lock:
            if job.state == 'cancelling' and changes.get('state') not in (None, *TERMINAL_STATES, 'finishing'):
                changes.pop('state', None)
            for name, value in changes.items():
                setattr(job, name, value)
        self._emit(job)

    def _run(self, job):
        state, detail, status = 'failed', '寄送失败', None
        try:
            with api_session(self.observe_quota, job.cancel):
                url, path, level, picture, lyrics = self._resolve(job)
                job.path, job.level = path, level
                check_cancel()
                self._update(job, state='downloading', detail=f'正在寄送 · {QUALITY_LABELS.get(level, level)}')
                last = 0.0
                started = time.monotonic()

                def progress(done, total):
                    nonlocal last
                    now = time.monotonic()
                    if now - last < 0.25 and (not total or done < total):
                        return
                    last = now
                    speed = done / max(now - started, 0.01)
                    self._update(job, done_bytes=done, total_bytes=total, speed=speed,
                                 pct=min(100.0, done * 100 / total) if total else 0)

                stream_download(url, path, progress=progress, cancel=job.cancel)
            # Complete audio is committed; finish metadata even if cancellation arrives.
            self._update(job, state='finishing', detail='封缄：写入歌词、封面与标签', pct=100)
            with api_session(self.observe_quota):
                job.flags = embed_song_data(job.key, path, job.song['platform'], job.song,
                                            lrc=lyrics, pic_url=picture or cover_url_for(job.song),
                                            want_lyric=job.settings.lyric or job.settings.ios,
                                            want_cover=job.settings.cover, sidecar_lrc=job.settings.ios)
            state, detail = 'done', '已送达'
        except FileExistsError as error:
            job.path = str(error.args[0]) if error.args else job.path
            state, detail = 'skipped', '书信匣里已有同名的信，已保留原件'
        except DownloadCancelled:
            state, detail = 'cancelled', '已撤回，未完成的临时文件已清理'
        except ApiError as error:
            state, detail, status = 'failed', safe_error(error), error.status
        except Exception as error:
            state, detail = 'failed', safe_error(error)
        finally:
            self._finish(job, state, detail, status)

    def _resolve(self, job):
        song, settings = job.song, job.settings
        platform = song['platform']
        levels = QUALITY_OPTIONS[platform]
        quality = settings.qualities.get(platform, levels[0])
        start = levels.index(quality) if quality in levels else 0
        result = None
        for level in levels[start:]:
            check_cancel()
            self._update(job, detail=f'尝试 {QUALITY_LABELS.get(level, level)}')
            try:
                result = RESOLVE[platform](job.key, song['id'], level)
            except ApiError as error:
                # Only "no such quality" degrades; auth/quota/outage stop immediately.
                if error.status != 404:
                    raise
                continue
            if result and result.get('url'):
                break
        else:
            raise RuntimeError('所有可用音质均无下载地址，请稍后重试或换个平台')
        level = result.get('level') or level
        artist = sanitize(song.get('artist')) if song.get('artist') else ''
        name = sanitize(song.get('name') or song['id'])
        folder = settings.out_dir
        if (settings.subfolders or settings.ios) and artist:
            folder = os.path.join(folder, artist)
        if settings.ios and song.get('album'):
            folder = os.path.join(folder, sanitize(song['album']))
        os.makedirs(folder, exist_ok=True)
        filename = sanitize(f'{artist} - {name}' if artist else name) + guess_ext(result['url'], result.get('format'))
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            raise FileExistsError(path)
        return result['url'], path, level, result.get('picUrl') or result.get('cover'), result.get('lrc')

    def _finish(self, job, state, detail, status):
        stopped = []
        with self._lock:
            self.running -= 1
            job.state, job.detail, job.finished = state, detail, time.time()
            if state == 'done':
                job.pct = 100
            if status in STOP_ALL | STOP_PLATFORM:
                for pending in self.jobs:
                    same_service = pending.song['platform'] == job.song['platform']
                    if pending.state == 'queued' and pending.key == job.key and (status in STOP_ALL or same_service):
                        pending.state = 'failed'
                        pending.detail = f'暂缓寄送：{detail} · 修复后可重试'
                        pending.finished = time.time()
                        stopped.append(pending)
        if self.closing:
            return
        self.history.add(job.history_record())
        self._emit(job)
        for pending in stopped:
            self.history.add(pending.history_record())
            self._emit(pending)
        if stopped:
            self.bus.publish('notice', {'level': 'warning',
                                        'text': f'接口暂不可用，已暂缓 {len(stopped)} 封排队的信：{detail}'})
        self._pump()
        if not self.active():
            counts = self.summary()['counts']
            self.bus.publish('drained', counts)


QQ_COVER_TPL = 'https://y.gtimg.cn/music/photo_new/T002R300x300M000%s.jpg'


def cover_url_for(song):
    """Cover URL from fields search/playlist already returned — never spends quota."""
    if not song:
        return None
    url = song.get('picUrl') or song.get('cover')
    if url:
        return url
    if song.get('album_mid'):
        return QQ_COVER_TPL % song['album_mid']
    return None
