"""Violet 本地服务：仅监听 127.0.0.1，为桌面窗口提供 JSON 接口、SSE 事件与媒体文件。

每次启动生成随机令牌；除静态页面外，所有请求都必须携带令牌，
避免本机其他网页借浏览器访问本服务。
"""
from collections import OrderedDict
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import queue
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

import chksz_dl as dl
import violet_backup as backup
from violet_core import (APP_VERSION, DATA_DIR, IMAGE_EXTS, PLATFORM_LABEL, QUALITY_LABELS, QUALITY_OPTIONS,
                         DownloadManager, EventBus, History, KeyStore, Settings, resolve_dir, safe_error)
from violet_desk import Conflict, Desk
from violet_geese import Geese, RouteError
from violet_letters import CHART_CATALOG, Letters, Plays, parse_playlist_link
from violet_shelf import Shelf
from violet_library import AUDIO_MIME, Library, read_cover, read_lyrics, recycle, sidecars
from violet_shelf import song_key

if getattr(sys, 'frozen', False):
    WEB_DIR = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)) / 'web' / 'dist'
else:
    WEB_DIR = Path(__file__).resolve().parent / 'web' / 'dist'

IMAGE_HOSTS = ('.126.net', '.gtimg.cn', '.qq.com', '.kugou.com', '.kgimg.com', '.chksz.com', '.chksz.top')
IMAGE_CACHE_LIMIT = 300
IMAGE_CACHE_BYTES = 64 * 1024 * 1024
IMAGE_MAX_BYTES = 8 * 1024 * 1024
PHOTO_MAX_BYTES = 12 * 1024 * 1024
PHOTO_TYPES = {b'\xff\xd8\xff': '.jpg', b'\x89PNG': '.png', b'RIFF': '.webp', b'GIF8': '.gif'}
REMINDER_INTERVAL = 20
GEESE_INTERVAL = 60


def image_host_allowed(url):
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or '').lower()
    return (parsed.scheme in ('http', 'https') and parsed.port in (None, 80, 443)
            and any(host.endswith(h) or host == h[1:] for h in IMAGE_HOSTS))


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a cover's redirect only while it stays on the music CDNs."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not image_host_allowed(newurl):
            raise PermissionError('图片跳转到了不允许的地址')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


IMAGE_OPENER = urllib.request.build_opener(_CheckedRedirect)


class VioletService:
    """Application state shared by all request threads."""

    def __init__(self, settings=None, keys=None, history=None, library=None, plays=None, letters=None, desk=None,
                 data_dir=None, shelf=None, geese=None):
        self.token = secrets.token_urlsafe(24)
        self.bus = EventBus()
        self.data_dir = Path(data_dir or DATA_DIR)
        self.settings = settings or Settings.load()
        self.keys = keys or KeyStore()
        self.history = history or History()
        self.library = library or Library()
        self.plays = plays or Plays()
        self.desk = desk or Desk()
        self.letters = letters or Letters(self.library, self.plays)
        self.letters.context = self.desk.letter_notes
        self.shelf = shelf or Shelf(self.desk)
        self.letters.favored = lambda: set(self.shelf.pressed_ids())
        self.geese = geese or Geese(self.desk, self.data_dir, publish=self.bus.publish, notify=self._notify)
        self.letters.geese = self.geese.paragraph
        self.letters.sources = lambda: self.settings.letter_sources()
        self._letter_lock = threading.Lock()
        self.downloads = DownloadManager(self.bus, self.history)
        self.recycle = recycle
        self.now_playing = None
        self.hooks = {}
        self.window_state = {'frameless': False, 'maximized': False}
        self._images = OrderedDict()
        self._image_bytes = 0
        self._image_lock = threading.Lock()
        self._settings_lock = threading.Lock()
        self._backup_lock = threading.Lock()
        self._stopping = threading.Event()
        self.backup_state = {'running': False, 'last': None, 'error': ''}

    # ------------------------------------------------------------ state

    def state(self):
        return {
            'version': APP_VERSION,
            'settings': self.settings.to_dict(),
            'key': self.keys.status(),
            'quota': self.downloads.quota,
            'jobs': self.downloads.snapshot(),
            'history': self.history.snapshot(),
            'platforms': PLATFORM_LABEL,
            'qualities': QUALITY_OPTIONS,
            'quality_labels': QUALITY_LABELS,
            'chart_catalog': CHART_CATALOG,
            'window': bool(self.hooks.get('pick_folder')),
            'frame': dict(self.window_state),
            'tray': bool(self.hooks.get('tray')),
            'today': date.today().isoformat(),
            'history_error': self.history.save_error,
        }

    def update_settings(self, data):
        """Merge only the fields that were sent, so two quick changes never overwrite each other."""
        with self._settings_lock:
            settings = Settings.from_dict(data, base=self.settings)
            out_dir = resolve_dir(settings.out_dir)
            os.makedirs(out_dir, exist_ok=True)
            if settings.backup_dir:
                os.makedirs(settings.backup_dir, exist_ok=True)
            settings.save()
            library_changed = settings.library_roots() != self.settings.library_roots()
            self.settings = settings
        if library_changed:
            self.library.tracks = {}  # the next library request rescans
        self.bus.publish('settings', settings.to_dict())
        if 'tray' in data and self.hooks.get('tray'):
            self.hooks['tray'](settings.tray)
        if {'desktop_lyrics', 'lyrics_locked'} & set(data) and self.hooks.get('lyrics'):
            self.hooks['lyrics'](settings)
        return settings

    def set_now_playing(self, data):
        """What the player is singing, for the desktop lyrics window (which has no player of its own)."""
        lines = [[float(t), str(text)[:200]] for t, text in (data.get('lines') or [])[:800]
                 if isinstance(t, (int, float))]
        self.now_playing = {'title': str(data.get('title') or '')[:200], 'artist': str(data.get('artist') or '')[:200],
                            'lines': lines, 'plain': [str(p)[:200] for p in (data.get('plain') or [])[:4]],
                            'playing': bool(data.get('playing')), 'time': float(data.get('time') or 0),
                            'at': time.time()}
        self.bus.publish('lyrics', self.now_playing)
        return {'ok': True}

    # ------------------------------------------------------------ background work

    def start_background(self):
        """Reminder clock and the daily backup; the desktop app calls this once."""
        threading.Thread(target=self._reminder_loop, name='violet-reminders', daemon=True).start()
        threading.Thread(target=self._geese_loop, name='violet-geese', daemon=True).start()
        if backup.last_backup_day(self.data_dir) != date.today():
            threading.Thread(target=self.run_backup, args=('每日',), name='violet-backup', daemon=True).start()

    def _reminder_loop(self):
        delay = 3  # first look soon after start, to deliver what was missed while closed
        while not self._stopping.wait(delay):
            delay = REMINDER_INTERVAL
            try:
                self.check_reminders()
            except Exception as error:  # keep the clock running
                print(f'提醒检查失败：{error}', file=sys.stderr, flush=True)

    def _geese_loop(self):
        """鸿雁: look for due routes every minute (the first look soon after start, to catch up after being closed)."""
        delay = 8
        last_tidy = 0
        while not self._stopping.wait(delay):
            delay = GEESE_INTERVAL
            try:
                self.run_geese()
                if time.time() - last_tidy > 3600:
                    self.geese.tidy()
                    last_tidy = time.time()
            except Exception as error:  # keep the geese flying
                print(f'鸿雁取信失败：{error}', file=sys.stderr, flush=True)

    def run_geese(self, force=False):
        geese = self.geese
        if not geese.card():
            return {'new': 0}
        try:
            new = geese.fetch(force=force)
        except RuntimeError:
            return {'new': 0, 'busy': True}
        alert = geese.alerts()
        if new or force:
            self.bus.publish('geese', {'new': len(new), 'ids': new[:50], 'alert': alert})
        return {'new': len(new), 'alert': alert}

    def _notify(self, title, text):
        notify = self.hooks.get('notify')
        if notify:
            try:
                notify(title, text)
            except Exception:
                pass

    def check_reminders(self, now=None):
        fired = self.desk.due_reminders(now)
        for item in fired:
            title, text = reminder_text(item)
            self.bus.publish('reminder', dict(item, heading=title, text=text))
            notify = self.hooks.get('notify')
            if notify:
                try:
                    notify(title, text)
                except Exception:
                    pass
        return fired

    def run_backup(self, reason='手动'):
        if not self._backup_lock.acquire(blocking=False):
            raise RuntimeError('备份正在进行')
        self.backup_state['running'] = True
        try:
            result = backup.run(self.data_dir, self.desk, self.settings.backup_dir, reason)
            self.backup_state.update(last=time.time(), error=result['error'])
            return result
        except OSError as error:
            self.backup_state['error'] = f'备份失败：{error.strerror or error}'
            raise
        finally:
            self.backup_state['running'] = False
            self._backup_lock.release()
            self.bus.publish('backup', self.backups())

    def backup_if_changed(self):
        """On exit: snapshot again if anything was written since the last backup."""
        items = backup.list_backups(self.data_dir / 'backups')
        last = items[0]['time'] if items else 0
        watched = [self.desk.path, self.letters.path, self.history.path, self.plays.path]
        if any(p.exists() and p.stat().st_mtime > last for p in map(Path, watched)):
            return self.run_backup('退出')
        return None

    def backups(self):
        return {'local': backup.list_backups(self.data_dir / 'backups'),
                'sync': backup.list_backups(self.settings.backup_dir) if self.settings.backup_dir else [],
                'sync_dir': self.settings.backup_dir, 'data_dir': str(self.data_dir), **self.backup_state}

    def restore_backup(self, name, where):
        folder = self.data_dir / 'backups' if where == 'local' else Path(self.settings.backup_dir or '')
        if where not in ('local', 'sync') or not str(folder) or not backup._is_backup(str(name)):
            raise ValueError('找不到这份备份')
        path = folder / name
        if not path.is_file():
            raise LookupError('这份备份已经不在了')
        backup.check(path)
        self.run_backup('恢复前')
        with self._letter_lock, self._settings_lock:
            self.desk.close()
            try:
                backup.extract(path, self.data_dir)
            finally:
                self.desk.open()
                self.shelf = Shelf(self.desk)  # an older backup may predate the shelf tables
                self.geese = Geese(self.desk, self.data_dir, publish=self.bus.publish, notify=self._notify)
            self.settings = Settings.load()
            self.history = History(self.history.path)
            self.downloads.history = self.history
            self.plays = Plays(self.plays.path)
            context = self.letters.context
            self.letters = Letters(self.library, self.plays, self.letters.path)
            self.letters.context = context
            self.letters.favored = lambda: set(self.shelf.pressed_ids())
            self.letters.geese = self.geese.paragraph
            self.letters.sources = lambda: self.settings.letter_sources()
        self.bus.publish('restored', {'name': name})
        return {'ok': True}

    def save_photo(self, raw):
        if not raw:
            raise ValueError('没有收到图片')
        if len(raw) > PHOTO_MAX_BYTES:
            raise ValueError('图片太大了（上限 12 MB）')
        ext = next((e for magic, e in PHOTO_TYPES.items() if raw.startswith(magic)), None)
        if not ext or (ext == '.webp' and raw[8:12] != b'WEBP'):
            raise ValueError('只支持 jpg / png / webp / gif 图片')
        folder = self.data_dir / 'photos'
        folder.mkdir(parents=True, exist_ok=True)
        name = secrets.token_hex(8) + ext
        (folder / name).write_bytes(raw)
        return name

    def photo_path(self, name):
        if not re.fullmatch(r'[0-9a-f]{16}\.(jpg|png|webp|gif)', name or ''):
            raise LookupError('照片不存在')
        path = self.data_dir / 'photos' / name
        if not path.is_file():
            raise LookupError('照片不存在')
        return path

    def tracks(self):
        """The library index, scanned on first use so the shelf never mistakes an unscanned library for lost songs."""
        if not self.library.tracks:
            self.library.scan(self.settings.library_roots())
        return self.library.tracks

    def shelf_view(self):
        tracks = self.tracks()
        return {'pressed': self.shelf.pressed(tracks), 'bundles': self.shelf.bundles(tracks),
                'memberships': self.shelf.all_memberships()}

    def songs_for(self, data):
        """Songs to tuck into a bundle: library ids (looked up here) and/or not-yet-downloaded songs."""
        tracks = self.tracks()
        songs = []
        for tid in data.get('track_ids') or []:
            track = tracks.get(str(tid))
            if not track:
                raise LookupError('书信匣里找不到这首歌，可能已经挪走了')
            songs.append(track)
        for song in data.get('songs') or []:
            if isinstance(song, dict):
                songs.append({'title': song.get('title') or song.get('name'), 'artist': song.get('artist'),
                              'album': song.get('album'), 'position': song.get('position'),
                              'track_id': song.get('track_id')})
        return songs

    def press(self, data):
        tid = str(data.get('track_id') or '')
        if data.get('press', True):
            track = self.tracks().get(tid)
            if not track:
                raise LookupError('书信匣里找不到这首歌')
            row = self.shelf.press(track, data.get('note'))
        else:
            row = None
            self.shelf.unpress(tid)
        return {'pressed': row, 'ids': self.shelf.pressed_ids()}

    # ------------------------------------------------------------ sending songs back

    def track_references(self, ids):
        """Where each song is kept, so the confirmation can say what goes with it."""
        tracks = self.tracks()
        pressed = set(self.shelf.pressed_ids())
        out = []
        for tid in ids:
            track = tracks.get(tid)
            if track:
                out.append({'id': tid, 'title': track['title'], 'artist': track['artist'],
                            'bundles': self.shelf.holding(tid), 'pressed': tid in pressed,
                            'replies': self.desk.replies_with_song(tid), 'twin': self._twin(track, tracks) is not None})
        return out

    @staticmethod
    def _twin(track, tracks, leaving=()):
        key = song_key(track.get('title'), track.get('artist'))
        return next((t['id'] for t in tracks.values() if t['id'] != track['id'] and t['id'] not in leaving
                     and song_key(t.get('title'), t.get('artist')) == key), None)

    def delete_tracks(self, ids):
        """Send songs back: into the Recycle Bin with their lyrics files, out of bundles and the pressed flowers."""
        tracks = self.tracks()
        removed, failed = [], []
        for tid in dict.fromkeys(str(i) for i in ids):
            track = tracks.get(tid)
            if not track:
                failed.append({'id': tid, 'error': '书信匣里找不到这首歌'})
                continue
            try:
                self.recycle([track['path'], *sidecars(track['path'])])
            except OSError as error:
                failed.append({'id': tid, 'title': track['title'], 'error': str(error)})
                continue
            removed.append(track)
        if removed:
            gone = [t['id'] for t in removed]
            self.library.forget(gone)
            self.shelf.forget_tracks(gone, self.library.tracks)
            self.history.forget_paths([t['path'] for t in removed])
            self.bus.publish('history', self.history.snapshot())
        return {'removed': [t['id'] for t in removed], 'failed': failed}

    def duplicates(self):
        """Songs the library holds more than once, best copy first: lossless, then bitrate, then length."""
        groups = {}
        for track in self.tracks().values():
            groups.setdefault(song_key(track.get('title'), track.get('artist')), []).append(track)
        out = []
        for key, items in groups.items():
            if len(items) < 2:
                continue
            copies = []
            for t in items:
                seconds = (t.get('duration') or 0) / 1000
                kbps = round(t.get('size', 0) * 8 / seconds / 1000) if seconds else 0
                copies.append({k: t.get(k) for k in ('id', 'title', 'artist', 'album', 'ext', 'size', 'duration',
                                                      'has_cover', 'has_lyrics', 'mtime', 'folder')}
                              | {'kbps': kbps, 'lossless': t.get('ext') in ('flac', 'wav')})
            copies.sort(key=lambda c: (not c['lossless'], -c['kbps'], -(c['duration'] or 0)))
            lengths = [c['duration'] or 0 for c in copies]
            out.append({'key': key, 'title': copies[0]['title'], 'artist': copies[0]['artist'], 'copies': copies,
                        # Very different lengths are probably different versions (live, remix), not mistakes.
                        'versions': max(lengths) - min(lengths) > 15000})
        out.sort(key=lambda g: (g['versions'], g['artist'].lower(), g['title'].lower()))
        return out

    def record_play(self, tid):
        entry = self.plays.record(tid)
        track = self.library.tracks.get(tid)
        if track:
            self.desk.record_listen(track)
        return entry

    def search(self, keyword, platform, page=0):
        """One page of results. NetEase pages by offset, QQ widens to 50, Kugou has a single page."""
        key = self._require_key()
        warnings = []
        page = max(0, int(page or 0))
        with dl.api_session(self.downloads.observe_quota):
            if platform == 'all':
                if page == 0:
                    songs = dl.search_all(key, keyword, on_error=warnings.append)
                    more = True
                else:
                    songs = [dict(s, platform='netease')
                             for s in dl.SEARCH['netease'](key, keyword, limit=10, offset=page * 10)]
                    more = len(songs) >= 10
                    if page == 1:
                        try:
                            songs += [dict(s, platform='qq') for s in dl.SEARCH['qq'](key, keyword, num=50)]
                        except dl.ApiError as error:
                            warnings.append(f'QQ音乐: {error}')
            elif platform == 'netease':
                songs = [dict(s, platform=platform)
                         for s in dl.SEARCH['netease'](key, keyword, limit=20, offset=page * 20)]
                more = len(songs) >= 20
            elif platform == 'qq':
                songs = [dict(s, platform=platform) for s in dl.SEARCH['qq'](key, keyword, num=20 if page == 0 else 50)]
                more = page == 0 and len(songs) >= 20
            elif platform == 'kugou':
                songs = [dict(s, platform=platform) for s in dl.SEARCH['kugou'](key, keyword)] if page == 0 else []
                more = False
            else:
                raise ValueError('未知平台')
        return {'songs': songs, 'page': page, 'has_more': more, 'warnings': [safe_error(w) for w in warnings]}

    def today_letter(self):
        with self._letter_lock:
            letter = self.letters.today_letter(self.settings.library_roots())
            if letter and not letter.get('opened'):
                letter = self.letters.refresh_geese(letter['date']) or letter
            return letter

    def portal_login(self, portal_id):
        """Open the school's own login page in a window; keep only the session it hands back."""
        portal = self.geese.portals().get(portal_id)
        if not portal:
            raise LookupError('没有这个门户')
        login = self.hooks.get('login')
        if not login:
            raise RuntimeError('只有桌面窗口里可以登录门户')
        cookies = login(portal['login'], portal['done'], f'登录 · {portal["name"]}')
        if not cookies:
            raise RuntimeError('登录窗口关上了，没有登录成功')
        self.geese.sessions.save(portal_id, cookies)
        with self.desk._tx() as db:
            db.execute("UPDATE geese_routes SET next_fetch = 0, error = NULL, fails = 0 "
                       "WHERE json_extract(data, '$.login') = ?", (portal_id,))
        self.bus.publish('geese-login', {'portal': portal_id, 'signed_in': True})
        return self.geese.sessions.status(portal_id)

    def portrait_file(self):
        path = self.settings.portrait_path
        if (self.settings.portrait != 'custom' or not path or not os.path.isfile(path)
                or not path.lower().endswith(IMAGE_EXTS)):
            raise LookupError('没有自定义背景立绘')
        return path

    def playlist(self, raw, platform):
        pid = dl.parse_playlist_id(raw)
        if 'music.163.com' in raw or '163cn.tv' in raw:
            platform = 'netease'
        elif 'y.qq.com' in raw or 'qq.com' in raw:
            platform = 'qq'
        if platform == 'qq':
            info, raw_songs = dl.fetch_qq_playlist(pid)
            songs = dl.normalize_qq_tracks(raw_songs)
            title = info.get('title') or 'QQ 歌单'
            cover = info.get('picurl') or info.get('headurl') or ''
            if not songs:
                raise RuntimeError('歌单为空或未公开。私人歌单请先在 QQ 音乐里设为公开。')
        elif platform == 'netease':
            key = self._require_key()
            with dl.api_session(self.downloads.observe_quota):
                info, songs = dl.fetch_netease_playlist(key, pid)
            title = info.get('name') or '网易云歌单'
            cover = songs[0].get('picUrl', '') if songs else ''
        else:
            raise ValueError('歌单只支持 QQ 音乐与网易云')
        songs = [dict(song, platform=platform) for song in songs]
        return {'id': pid, 'platform': platform, 'title': title, 'cover': cover, 'songs': songs}

    def verify_key(self):
        key = self._require_key()
        with dl.api_session(self.downloads.observe_quota):
            body, _ = dl.api('/api/163_search', {'keyword': '晴天', 'limit': 1, 'offset': 0}, key)
            dl.check_business(body)
        return self.downloads.quota

    def _require_key(self):
        if not self.keys.key:
            raise PermissionError('需要先配置 API Key')
        return self.keys.key

    def image(self, url):
        if not image_host_allowed(url):
            raise PermissionError('不允许的图片来源')
        with self._image_lock:
            if url in self._images:
                self._images.move_to_end(url)
                return self._images[url]
        request = urllib.request.Request(url, headers={'User-Agent': dl.USER_AGENT})
        with IMAGE_OPENER.open(request, timeout=15) as response:
            mime = response.headers.get('Content-Type', 'image/jpeg').split(';')[0].strip()
            if mime not in ('image/jpeg', 'image/png', 'image/webp', 'image/gif'):
                raise ValueError('不是图片')
            data = response.read(IMAGE_MAX_BYTES + 1)
        if len(data) > IMAGE_MAX_BYTES:
            raise ValueError('图片太大')
        with self._image_lock:
            if url not in self._images:
                self._images[url] = (data, mime)
                self._image_bytes += len(data)
            while self._images and (len(self._images) > IMAGE_CACHE_LIMIT or self._image_bytes > IMAGE_CACHE_BYTES):
                _, (old, _) = self._images.popitem(last=False)
                self._image_bytes -= len(old)
        return data, mime

    def reveal(self, path):
        path = os.path.normpath(path)
        if not os.path.exists(path):
            raise FileNotFoundError('文件已不存在')
        if os.name == 'nt':
            if os.path.isdir(path):
                os.startfile(path)
            else:
                subprocess.Popen(['explorer', '/select,', path])
        else:
            subprocess.Popen(['xdg-open', path if os.path.isdir(path) else os.path.dirname(path)])

    def shutdown(self):
        self._stopping.set()
        self.downloads.shutdown()


def reminder_text(item):
    when = f'{item["when"]} ' if item.get('when') else ''
    late = '（Violet 关着时错过了）' if item.get('late') else ''
    if item['kind'] == 'commission':
        who = f'委托人：{item["client"]}　' if item.get('client') else ''
        return f'委托提醒 · {when or "今天"}'.strip(), f'「{item["title"]}」该动笔了。{who}{late}'.strip()
    if item['kind'] == 'anniversary':
        return '纪念日', f'今天是「{item["title"]}」。{late}'
    place = f'地点：{item["place"]}　' if item.get('place') else ''
    return f'约定 · {when or item["date"]}'.strip(), f'「{item["title"]}」{place}{late}'.strip()


class Handler(BaseHTTPRequestHandler):
    server_version = 'Violet/' + APP_VERSION
    protocol_version = 'HTTP/1.1'

    @property
    def service(self):
        return self.server.service

    def log_message(self, fmt, *args):
        pass

    # ------------------------------------------------------------ helpers

    def _query(self):
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    def _param(self, name, default=''):
        return self._query().get(name, [default])[0]

    def _authorized(self):
        token = self.headers.get('X-Violet-Token') or self._param('t')
        return secrets.compare_digest(token or '', self.service.token)

    def _send(self, status, body=b'', mime='application/json; charset=utf-8', headers=None):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _json(self, data, status=200):
        self._send(status, json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _error(self, message, status=400, code=None):
        self._json({'error': message, 'code': code}, status)

    def _read_body(self):
        """Consume the request body up front so a keep-alive connection never sees leftovers."""
        length = int(self.headers.get('Content-Length') or 0)
        if length > PHOTO_MAX_BYTES + 1024:
            self.close_connection = True
            self._raw = None
            return
        self._raw = self.rfile.read(length) if length else b''

    def _body(self):
        raw = getattr(self, '_raw', b'')
        if raw is None:
            raise ValueError('请求过大')
        data = json.loads((raw or b'{}').decode('utf-8') or '{}')
        if not isinstance(data, dict):
            raise ValueError('请求格式错误')
        return data

    # ------------------------------------------------------------ dispatch

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith('/api/'):
            return self._static(path)
        if not self._authorized():
            return self._error('未授权', 403)
        routes = {
            '/api/state': lambda: self._json(self.service.state()),
            '/api/events': self._events,
            '/api/search': self._search,
            '/api/playlist': self._playlist,
            '/api/img': self._image,
            '/api/library': self._library,
            '/api/letters': lambda: self._json({'letters': self.service.letters.list()}),
            '/api/letters/today': lambda: self._json(self.service.today_letter()),
            '/api/portrait': self._portrait,
            '/api/desk/today': lambda: self._json(self.service.desk.today_view()),
            '/api/commissions': lambda: self._json({'commissions': self.service.desk.commissions(),
                                                    'clients': self.service.desk.clients()}),
            '/api/calendar': self._calendar,
            '/api/day': self._day,
            '/api/replies': lambda: self._json({'replies': self.service.desk.replies(),
                                                'weeks': self.service.desk.sealed_weeks()}),
            '/api/weekly': lambda: self._json(self.service.desk.weekly(self._param('week'))),
            '/api/backups': lambda: self._json(self.service.backups()),
            '/api/shelf': lambda: self._json(self.service.shelf_view()),
            '/api/geese': lambda: self._json(self.service.geese.cabinet()),
            '/api/geese/drawer': lambda: self._json({'letters': self.service.geese.drawer(
                self._param('box'), self._param('q').strip())}),
            '/api/library/duplicates': lambda: self._json({'groups': self.service.duplicates()}),
            '/api/lyrics/now': lambda: self._json({'now': self.service.now_playing,
                                                   'settings': self.service.settings.to_dict()}),
            '/api/geese/routes': lambda: self._json({'routes': self.service.geese.routes(),
                                                     'portals': self.service.geese.portals()}),
        }
        if path in routes:
            return self._guard(routes[path])
        parts = path.strip('/').split('/')
        if len(parts) == 4 and parts[:2] == ['api', 'library']:
            return self._guard(lambda: self._library_item(parts[2], parts[3]))
        if len(parts) == 3 and parts[:2] == ['api', 'photos']:
            return self._guard(lambda: self._photo(parts[2]))
        if len(parts) == 3 and parts[:2] == ['api', 'replies']:
            return self._guard(lambda: self._json(self._found(self.service.desk.reply(parts[2]))))
        if len(parts) == 3 and parts[:2] == ['api', 'bundles']:
            return self._guard(lambda: self._json(self.service.shelf.bundle(parts[2], self.service.tracks())))
        if len(parts) in (4, 5) and parts[:3] == ['api', 'geese', 'letters']:
            if len(parts) == 5 and parts[4] == 'words':
                return self._guard(lambda: self._json(self.service.geese.words(parts[3])))
            return self._guard(lambda: self._json(self.service.geese.letter(parts[3], self._param('peek') != '1')))
        self._error('未找到', 404)

    def do_POST(self):
        self._read_body()
        path = urllib.parse.urlparse(self.path).path
        if not self._authorized():
            return self._error('未授权', 403)
        routes = {
            '/api/settings': self._post_settings,
            '/api/key': self._post_key,
            '/api/key/forget': self._forget_key,
            '/api/key/verify': self._verify_key,
            '/api/downloads': self._post_downloads,
            '/api/downloads/cancel': self._cancel,
            '/api/downloads/retry': self._retry,
            '/api/downloads/clear': self._clear,
            '/api/history/remove': self._history_remove,
            '/api/history/clear': self._history_clear,
            '/api/reveal': self._reveal,
            '/api/pick-folder': self._pick_folder,
            '/api/window': self._window,
            '/api/letters/update': self._letter_update,
            '/api/pick-image': self._pick_image,
            '/api/commissions': lambda: self._json(self.service.desk.create_commission(self._body())),
            '/api/appointments': lambda: self._json(self.service.desk.create_appointment(self._body())),
            '/api/replies': lambda: self._json(self.service.desk.create_reply(self._body())),
            '/api/photos': lambda: self._json({'name': self.service.save_photo(self._raw)}),
            '/api/export-image': self._export_image,
            '/api/lyrics/now': lambda: self._json(self.service.set_now_playing(self._body())),
            '/api/focus': self._focus_free,
            '/api/backups/run': lambda: self._json(self.service.run_backup('手动')),
            '/api/backups/restore': self._restore,
            '/api/pressed': lambda: self._json(self.service.press(self._body())),
            '/api/library/references': lambda: self._json({'items': self.service.track_references(self._ids())}),
            '/api/library/delete': lambda: self._json(self.service.delete_tracks(self._ids())),
            '/api/bundles': self._create_bundle,
            '/api/geese/card': lambda: self._json(self.service.geese.save_card(self._body())),
            '/api/geese/trial': lambda: self._json(self.service.geese.trial(self._body())),
            '/api/geese/fetch': lambda: self._json(self.service.run_geese(force=True)),
            '/api/geese/packs/preview': lambda: self._json(self.service.geese.preview_pack(self._body().get('pack'))),
            '/api/geese/packs/install': self._install_pack,
        }
        if path in routes:
            return self._guard(routes[path])
        parts = path.strip('/').split('/')
        if len(parts) == 4 and parts[:2] == ['api', 'library'] and parts[3] == 'played':
            return self._guard(lambda: self._played(parts[2]))
        if len(parts) >= 4 and parts[1] == 'geese':
            return self._guard(lambda: self._geese_post(parts[2:]))
        if len(parts) in (3, 4) and parts[1] == 'bundles':
            return self._guard(lambda: self._bundle_post(parts[2], parts[3] if len(parts) == 4 else ''))
        if len(parts) in (3, 4) and parts[1] in ('commissions', 'appointments', 'replies', 'weekly'):
            return self._guard(lambda: self._desk_post(parts[1], parts[2], parts[3] if len(parts) == 4 else ''))
        self._error('未找到', 404)

    def _guard(self, action):
        try:
            action()
        except RouteError as error:
            self._error(str(error), 400, 'route')
        except Conflict as error:
            self._json({'error': str(error), 'code': 'conflict', 'current': error.current}, 409)
        except PermissionError as error:
            self._error(safe_error(error), 401, 'no_key' if 'Key' in str(error) else 'forbidden')
        except dl.ApiError as error:
            self._error(safe_error(error), 502, error.status)
        except (ValueError, LookupError, RuntimeError, OSError) as error:
            self._error(safe_error(error), 400)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as error:  # Surface unexpected errors instead of dropping the socket.
            self._error(safe_error(f'{type(error).__name__}: {error}'), 500)

    # ------------------------------------------------------------ catalog

    def _search(self):
        keyword = self._param('q').strip()
        if not keyword:
            raise ValueError('请输入歌名、歌手或歌词')
        self._json(self.service.search(keyword, self._param('platform', 'netease'), self._param('page', '0') or 0))

    def _playlist(self):
        raw = self._param('src').strip()
        if not raw:
            raise ValueError('请粘贴歌单链接或 ID')
        self._json(self.service.playlist(raw, self._param('platform', 'qq')))

    def _image(self):
        data, mime = self.service.image(self._param('u'))
        self._send(200, data, mime, {'Cache-Control': 'max-age=86400'})

    # ------------------------------------------------------------ settings and key

    def _post_settings(self):
        self._json(self.service.update_settings(self._body()).to_dict())

    def _post_key(self):
        data = self._body()
        self.service.keys.set(data.get('key'), bool(data.get('remember')))
        status = self.service.keys.status()
        self.service.bus.publish('key', status)
        self._json(status)

    def _forget_key(self):
        self.service.keys.forget()
        status = self.service.keys.status()
        self.service.bus.publish('key', status)
        self._json(status)

    def _verify_key(self):
        self._json({'quota': self.service.verify_key()})

    # ------------------------------------------------------------ downloads

    def _post_downloads(self):
        songs = self._body().get('songs') or []
        if not isinstance(songs, list) or not songs:
            raise ValueError('没有要寄送的歌曲')
        added, duplicates = self.service.downloads.enqueue(songs, self.service.settings, self.service.keys.key)
        self._json({'added': len(added), 'duplicates': duplicates})

    def _cancel(self):
        self._json({'cancelled': self.service.downloads.cancel(self._body().get('id'))})

    def _retry(self):
        data = self._body()
        key = self.service.keys.key
        if data.get('record'):
            count = self.service.downloads.retry_record(data['record'], key)
        else:
            count = self.service.downloads.retry(key, data.get('id'))
        self._json({'retried': count})

    def _clear(self):
        self._json({'removed': self.service.downloads.clear_finished()})

    def _history_remove(self):
        ids = self._body().get('ids') or []
        self.service.history.remove([i for i in ids if isinstance(i, str)])
        self.service.bus.publish('history', self.service.history.snapshot())
        self._json({'ok': True})

    def _history_clear(self):
        self.service.history.clear()
        self.service.bus.publish('history', [])
        self._json({'ok': True})

    def _reveal(self):
        data = self._body()
        if data.get('track'):
            path = self.service.library.path_for(data['track'])
        elif data.get('record'):
            record = self.service.history.get(data['record']) or {}
            path = record.get('path')
        elif data.get('folder') == 'out':
            path = resolve_dir(self.service.settings.out_dir)
            os.makedirs(path, exist_ok=True)
        elif data.get('folder') == 'data':
            path = str(self.service.data_dir)
        elif data.get('folder') == 'sync' and self.service.settings.backup_dir:
            path = self.service.settings.backup_dir
        else:
            path = None
        if not path:
            raise LookupError('找不到这封信')
        self.service.reveal(path)
        self._json({'ok': True})

    def _window(self):
        hook = self.service.hooks.get('window')
        if not hook:
            raise RuntimeError('只有桌面窗口支持这个操作')
        data = self._body()
        action = data.get('action')
        if action not in ('begin', 'minimize', 'maximize', 'restore', 'toggle', 'close', 'show'):
            raise ValueError('未知的窗口操作')
        hook(action, data.get('edge'))
        self._json({'ok': True})

    def _letter_update(self):
        data = self._body()
        changes = {k: bool(data[k]) for k in ('opened', 'starred') if k in data}
        self._json(self.service.letters.update(str(data.get('date')), **changes))

    def _played(self, tid):
        if not self.service.library.path_for(tid):
            return self._error('曲目不存在', 404)
        self._json(self.service.record_play(tid))

    # ------------------------------------------------------------ desk

    @staticmethod
    def _found(record):
        if record is None:
            raise LookupError('这条记录不存在')
        return record

    def _calendar(self):
        month = self._param('month') or date.today().strftime('%Y-%m')
        try:
            year, number = (int(x) for x in month.split('-'))
            date(year, number, 1)
        except ValueError:
            raise ValueError('月份格式应为 YYYY-MM') from None
        days = self.service.desk.month(year, number)
        if days:
            pressed = self.service.shelf.pressed_days(date.fromisoformat(days[0]['date']), date.fromisoformat(days[-1]['date']))
            for day in days:
                day['pressed'] = pressed.get(day['date'], 0)
        self._json({'month': f'{year}-{number:02d}', 'days': days})

    def _day(self):
        day = self._param('date') or date.today().isoformat()
        detail = self.service.desk.day(day)
        detail['letter'] = self.service.letters.get(day[:10])
        detail['pressed'] = self.service.shelf.pressed_on(day[:10])
        detail['geese'] = self.service.geese.due_on(day[:10])
        self._json(detail)

    def _desk_post(self, kind, record_id, action):
        desk, data = self.service.desk, self._body()
        if kind == 'weekly':
            if action != 'seal':
                raise LookupError('未知的操作')
            return self._json(desk.seal_week(record_id, data.get('note', '')))
        if action in ('delete', 'restore'):
            desk.delete(kind, record_id, restore=action == 'restore')
            return self._json({'ok': True})
        if kind == 'commissions':
            if action == '':
                return self._json(desk.update_commission(record_id, data))
            if action == 'complete':
                item, spawned = desk.complete_commission(record_id, bool(data.get('done', True)))
                return self._json({'commission': item, 'spawned': spawned})
            if action == 'focus':
                return self._json(desk.add_focus(record_id, data.get('seconds', 0), data.get('started')))
        elif kind == 'appointments' and action == '':
            return self._json(desk.update_appointment(record_id, data))
        elif kind == 'replies':
            if action == '':
                return self._json(desk.update_reply(record_id, data))
            if action == 'seal':
                return self._json(desk.seal_reply(record_id, data.get('recipient', 'violet'), data.get('deliver_on'),
                                                  data.get('revision'), data.get('stationery')))
            if action == 'unseal':
                return self._json(self._found(desk.unseal_reply(record_id)))
            if action == 'open':
                return self._json(self._found(desk.open_reply(record_id)))
        raise LookupError('未知的操作')

    def _create_bundle(self):
        service, data = self.service, self._body()
        songs = service.songs_for(data)
        bundle = service.shelf.create_bundle(data, service.tracks())
        if songs:
            bundle = service.shelf.add(bundle['id'], songs, service.tracks())['bundle']
        self._json(bundle)

    def _bundle_post(self, bid, action):
        service, data = self.service, self._body()
        shelf, tracks = service.shelf, service.tracks()
        if action == '':
            return self._json(shelf.update_bundle(bid, data, tracks))
        if action in ('delete', 'restore'):
            shelf.delete_bundle(bid, restore=action == 'restore')
            return self._json({'ok': True})
        if action == 'add':
            return self._json(shelf.add(bid, service.songs_for(data), tracks))
        if action == 'remove':
            return self._json(shelf.remove(bid, data.get('letter_ids'), tracks))
        if action == 'order':
            return self._json(shelf.reorder(bid, data.get('letter_ids'), tracks))
        raise LookupError('未知的操作')

    def _install_pack(self):
        data = self._body()
        pack = self.service.geese.install_pack(data.get('pack'), trust_ids=set(data.get('trust') or []))
        self._json({'pack': {k: pack[k] for k in ('id', 'name')}, 'routes': self.service.geese.routes()})

    def _geese_post(self, parts):
        geese, data = self.service.geese, self._body()
        kind, key = parts[0], parts[1]
        action = parts[2] if len(parts) > 2 else ''
        if kind == 'letters' and action == '':
            return self._json(geese.update_letter(key, data))
        if kind == 'letters' and action == 'teach':
            return self._json(geese.teach(key, data))
        if kind == 'routes' and action == '':
            return self._json(geese.set_route(key, data))
        if kind == 'packs' and action == 'remove':
            geese.remove_pack(key)
            return self._json({'routes': geese.routes()})
        if kind == 'portals' and action == 'login':
            return self._json(self.service.portal_login(key))
        if kind == 'portals' and action == 'logout':
            geese.sessions.forget(key)
            return self._json(geese.sessions.status(key))
        raise LookupError('未知的操作')

    def _focus_free(self):
        data = self._body()
        self.service.desk.add_focus(None, data.get('seconds', 0), data.get('started'))
        self._json({'ok': True})

    def _restore(self):
        data = self._body()
        self._json(self.service.restore_backup(str(data.get('name') or ''), data.get('where') or 'local'))

    def _photo(self, name):
        path = self.service.photo_path(name)
        mime = mimetypes.guess_type(str(path))[0] or 'image/jpeg'
        self._send(200, path.read_bytes(), mime, {'Cache-Control': 'max-age=31536000, immutable'})

    def _portrait(self):
        path = self.service.portrait_file()
        mime = mimetypes.guess_type(path)[0] or 'image/jpeg'
        self._send(200, Path(path).read_bytes(), mime, {'Cache-Control': 'no-store'})

    def _pick_image(self):
        picker = self.service.hooks.get('pick_image')
        if not picker:
            raise RuntimeError('只有桌面窗口里可以选择图片，请直接输入路径')
        self._json({'path': picker()})

    def _export_image(self):
        """A letter rendered to PNG in the page, saved where the person chooses."""
        saver = self.service.hooks.get('save_file')
        if not saver:
            raise RuntimeError('只有桌面窗口里可以另存图片')
        raw = self._raw or b''
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('不是一张 PNG 图片')
        name = re.sub(r'[\\/:*?"<>|]+', ' ', self._param('name') or 'Violet 的信.png').strip()[:80] or 'Violet 的信.png'
        path = saver(name if name.lower().endswith('.png') else name + '.png')
        if path:
            Path(path).write_bytes(raw)
        self._json({'path': path or ''})

    def _pick_folder(self):
        picker = self.service.hooks.get('pick_folder')
        if not picker:
            raise RuntimeError('只有桌面窗口里可以选择文件夹，请直接输入路径')
        self._json({'path': picker(self._body().get('initial') or '')})

    # ------------------------------------------------------------ library

    def _library(self):
        service = self.service
        if self._param('refresh') == '1' or not service.library.tracks:
            tracks = service.library.scan(service.settings.library_roots())
        else:
            tracks = service.library.list()
        self._json({'tracks': tracks, 'roots': service.settings.library_roots()})

    def _ids(self):
        ids = self._body().get('ids')
        if not isinstance(ids, list) or not ids or len(ids) > 500:
            raise ValueError('要退回哪些歌？')
        return [str(i) for i in ids]

    def _library_item(self, tid, kind):
        path = self.service.library.path_for(tid)
        if not path:
            return self._error('曲目不存在，请刷新书信匣', 404)
        if kind == 'audio':
            return self._file(path, AUDIO_MIME.get(os.path.splitext(path)[1].lower(), 'application/octet-stream'))
        if kind == 'cover':
            cover = read_cover(path)
            if not cover:
                return self._error('没有封面', 404)
            return self._send(200, cover[0], cover[1], {'Cache-Control': 'max-age=3600'})
        if kind == 'lyrics':
            return self._json({'lyrics': read_lyrics(path)})
        self._error('未找到', 404)

    def _file(self, path, mime):
        size = os.path.getsize(path)
        start, end = 0, size - 1
        status = 200
        header = self.headers.get('Range')
        if header and header.startswith('bytes='):
            first, _, last = header[6:].split(',')[0].partition('-')
            try:
                if first:
                    start = int(first)
                    end = min(int(last), size - 1) if last else size - 1
                else:
                    start = max(0, size - int(last))
                status = 206
            except ValueError:
                start, end = 0, size - 1
            if start > end or start >= size:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
        length = end - start + 1
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(length))
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if self.command == 'HEAD':
            return
        with open(path, 'rb') as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return
                remaining -= len(chunk)

    # ------------------------------------------------------------ events

    def _events(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()
        self.close_connection = True
        bus = self.service.bus
        subscription = bus.subscribe()
        try:
            self.wfile.write(b'retry: 1500\n\n')
            self.wfile.flush()
            while not self.server.stopping:
                try:
                    message = subscription.get(timeout=15)
                    payload = json.dumps(message, ensure_ascii=False)
                    self.wfile.write(f'data: {payload}\n\n'.encode('utf-8'))
                except queue.Empty:
                    self.wfile.write(b': keep-alive\n\n')
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            bus.unsubscribe(subscription)

    # ------------------------------------------------------------ static

    def _static(self, path):
        root = WEB_DIR.resolve()
        relative = urllib.parse.unquote(path).lstrip('/') or 'index.html'
        target = (root / relative).resolve()
        if root not in target.parents and target != root or not target.is_file():
            target = root / 'index.html'
        if not target.is_file():
            body = '前端尚未构建：请在 web 目录运行 npm run build'.encode('utf-8')
            return self._send(503, body, 'text/plain; charset=utf-8')
        mime = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
        if mime.startswith('text/') or mime in ('application/javascript', 'image/svg+xml'):
            mime += '; charset=utf-8'
        cache = 'max-age=31536000, immutable' if '/assets/' in path else 'no-store'
        self._send(200, target.read_bytes(), mime, {'Cache-Control': cache})


class VioletServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, service, port=0):
        super().__init__(('127.0.0.1', port), Handler)
        self.service = service
        self.stopping = False

    def handle_error(self, request, client_address):
        # The webview routinely drops idle keep-alive connections; that is not an error.
        error = sys.exc_info()[1]
        if isinstance(error, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server_address[1]}/?t={self.service.token}'

    def start(self):
        thread = threading.Thread(target=self.serve_forever, name='violet-http', daemon=True)
        thread.start()
        return thread

    def stop(self):
        self.stopping = True
        self.service.shutdown()
        self.shutdown()
        self.server_close()


mimetypes.add_type('font/woff2', '.woff2')
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')
