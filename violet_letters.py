"""每日来信：一句寄语、三首榜单新歌（书信匣里没有的）与一封「旧信」（很久没听的本地歌曲）。

- 寄语：内置精选库（data/quotes.json）为主；每三天尝试从「一言」诗词分类取一句有出处的，失败即用内置。
- 新歌：从设置里勾选的来源挑——网易云与 QQ 音乐的公开榜单、你粘贴的公开歌单、按你常听的歌手找；
  都走公开接口，不需要 Key、不耗额度，也不登录。每天挑几首可以在设置里定（1–5）。
- 旧信：按播放记录挑很久没听或从未播放的本地歌曲。
- 附言：昨天没办完的委托、今天的纪念日、周日的封存提醒（由书桌提供）。
信件与播放记录保存在用户数据目录；普通来信最多保留 400 封，收藏的信永远保留。
"""
from datetime import date, datetime
import json
from pathlib import Path
import random
import re
import sys
import threading
import time
import urllib.parse
import urllib.request

from violet_core import APP_DIR, DATA_DIR as USER_DIR, _write_json

if getattr(sys, 'frozen', False):
    DATA_DIR = Path(getattr(sys, '_MEIPASS', APP_DIR)) / 'data'
else:
    DATA_DIR = Path(__file__).resolve().parent / 'data'
LETTERS_FILE = USER_DIR / 'letters.json'
PLAYS_FILE = USER_DIR / 'plays.json'
LETTER_LIMIT = 400
CHARTS = [(62, '飙升榜'), (27, '新歌榜'), (26, '热歌榜')]
# Charts that can be ticked in settings: "platform:id" → name.
CHART_CATALOG = {
    'netease:19723756': '飙升榜', 'netease:3779629': '新歌榜', 'netease:2884035': '原创榜', 'netease:3778678': '热歌榜',
    'netease:2809513713': '欧美热歌榜', 'netease:5059644681': '日语榜', 'netease:991319590': '中文说唱榜',
    'netease:71384707': '古典榜',
    'qq:62': '飙升榜', 'qq:27': '新歌榜', 'qq:26': '热歌榜', 'qq:4': '流行指数榜', 'qq:5': '内地榜', 'qq:59': '香港地区榜',
    'qq:3': '欧美榜', 'qq:16': '韩国榜', 'qq:17': '日本榜',
}
DEFAULT_SOURCES = {'charts': ['netease:19723756', 'netease:3779629', 'qq:62', 'qq:27', 'qq:26'], 'taste': True,
                   'playlists': [], 'count': 3}
PLATFORM_NAME = {'qq': 'QQ 音乐', 'netease': '网易云'}
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Violet/4'
BROWSER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
OLD_AFTER_DAYS = 30

GREETINGS = ['亲爱的你：', '见字如面：', '致今天的你：', '展信佳：', '你好呀：']
CLOSINGS = ['愿今天的歌，替你说出想说的话。', '如果累了，就听一首歌再出发。', '今天也请好好照顾自己。',
            '把喜欢的旋律，留给值得的时刻。', '愿你在某一句歌词里，遇见自己。', '慢慢来，一切都来得及。']


def normalize(text):
    return re.sub(r'[\s\W_]+', '', str(text or '').lower())


def song_signature(name, artist):
    first = re.split(r'[/、,，&]| feat', str(artist or ''), 1)[0]
    return normalize(re.sub(r'[（(].*?[)）]', '', str(name or ''))) + '|' + normalize(first)


class Plays:
    """Last-played time and play count per library track id."""

    def __init__(self, path=None):
        self.path = Path(path or PLAYS_FILE)
        self._lock = threading.Lock()
        try:
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(self.data, dict):
                self.data = {}
        except (OSError, ValueError):
            self.data = {}

    def record(self, track_id):
        with self._lock:
            previous = self.data.get(track_id)
            entry = dict(previous or {'count': 0})
            entry['count'] = int(entry.get('count', 0)) + 1
            entry['last'] = time.time()
            self.data[track_id] = entry
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                _write_json(self.path, self.data)
            except OSError:
                if previous is None:
                    self.data.pop(track_id, None)
                else:
                    self.data[track_id] = previous
                raise
            return entry

    def last(self, track_id):
        return (self.data.get(track_id) or {}).get('last', 0)


def load_quotes():
    try:
        rows = json.loads((DATA_DIR / 'quotes.json').read_text(encoding='utf-8'))
        return [{'text': t, 'author': a, 'source': s, 'origin': 'builtin'} for t, a, s in rows if t]
    except (OSError, ValueError):
        return [{'text': '每一封信都会抵达，只是有的走得慢一些。', 'author': 'Violet 代笔', 'source': '', 'origin': 'builtin'}]


def fetch_hitokoto(timeout=4):
    """A line of classical poetry with a known source, or None."""
    url = 'https://v1.hitokoto.cn/?' + urllib.parse.urlencode({'c': 'i', 'encode': 'json', 'max_length': 48})
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode('utf-8'))
    text, source = (data.get('hitokoto') or '').strip(), (data.get('from') or '').strip()
    if not text or not source:
        return None
    return {'text': text, 'author': (data.get('from_who') or '').strip(), 'source': f'《{source.strip("《》")}》',
            'origin': 'hitokoto'}


def fetch_chart(top_id, num=60, timeout=15):
    payload = {'req_0': {'module': 'musicToplist.ToplistInfoServer', 'method': 'GetDetail',
                         'param': {'topId': top_id, 'offset': 0, 'num': num, 'period': ''}},
               'comm': {'ct': 24, 'cv': 0}}
    url = 'https://u.y.qq.com/cgi-bin/musicu.fcg?' + urllib.parse.urlencode(
        {'format': 'json', 'data': json.dumps(payload, ensure_ascii=False)})
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Referer': 'https://y.qq.com/'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode('utf-8'))
    data = (body.get('req_0') or {}).get('data') or {}
    songs = []
    for info in data.get('songInfoList') or []:
        album = info.get('album') or {}
        if not info.get('mid'):
            continue
        songs.append({'platform': 'qq', 'id': info['mid'], 'name': info.get('name') or '',
                      'artist': ', '.join(s.get('name', '') for s in info.get('singer') or []),
                      'album': album.get('name', ''), 'album_mid': album.get('mid', ''),
                      'duration': int(info.get('interval') or 0) * 1000})
    return songs, (data.get('data') or {}).get('period') or ''


def _netease(path, timeout=15):
    request = urllib.request.Request('https://music.163.com' + path,
                                     headers={'User-Agent': BROWSER_AGENT, 'Referer': 'https://music.163.com/'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode('utf-8'))
    if body.get('code') not in (200, None):
        raise RuntimeError(f'网易云接口返回 {body.get("code")}')
    return body


def _netease_song(t):
    # The playlist API names fields ar/al/dt; the older artist API spells them out.
    artists = t.get('ar') or t.get('artists') or []
    album = t.get('al') or t.get('album') or {}
    return {'platform': 'netease', 'id': str(t.get('id')), 'name': t.get('name') or '',
            'artist': ', '.join(a.get('name', '') for a in artists), 'album': album.get('name', ''),
            'picUrl': album.get('picUrl', ''), 'duration': int(t.get('dt') or t.get('duration') or 0)}


def fetch_netease_playlist(pid):
    """A public NetEase playlist or chart, without signing in: (name, songs)."""
    playlist = _netease(f'/api/v6/playlist/detail?id={int(pid)}&n=300').get('playlist') or {}
    return playlist.get('name') or '网易云歌单', [_netease_song(t) for t in playlist.get('tracks') or [] if t.get('id')]


def fetch_qq_playlist(pid):
    import chksz_dl as dl
    info, songs = dl.fetch_qq_playlist(pid)
    return info.get('title') or 'QQ 歌单', [dict(s, platform='qq') for s in dl.normalize_qq_tracks(songs)]


def fetch_artist_songs(artist):
    """An artist's well-loved songs on NetEase (public search + artist page)."""
    query = urllib.parse.urlencode({'s': artist, 'type': 100, 'limit': 3})
    found = (_netease(f'/api/search/get?{query}').get('result') or {}).get('artists') or []
    match = next((a for a in found if _plain(a.get('name')) == _plain(artist)), None)
    if not match:
        return []
    return [_netease_song(t) for t in _netease(f'/api/artist/{int(match["id"])}').get('hotSongs') or [] if t.get('id')]


def _plain(text):
    return re.sub(r'\s+', '', (text or '').casefold())


def parse_playlist_link(raw):
    """(platform, id) from a pasted NetEase or QQ playlist link."""
    raw = (raw or '').strip()
    platform = 'netease' if ('163.com' in raw or '163cn.tv' in raw) else 'qq' if 'qq.com' in raw else None
    match = re.search(r'(?:[?&#]|^)(?:id|disstid)=(\d+)', raw) or re.search(r'/playlist/(\d+)', raw)
    if not platform or not match:
        raise ValueError('认不出这个歌单链接：请粘贴网易云或 QQ 音乐的公开歌单链接')
    return platform, match.group(1)


class Letters:
    def __init__(self, library, plays, path=None, quotes=None, fetch=None, today=None):
        self.library = library
        self.plays = plays
        self.path = Path(path or LETTERS_FILE)
        self.quotes = quotes or load_quotes()
        self.fetch_chart = fetch or fetch_chart
        self.fetch_netease = fetch_netease_playlist
        self.fetch_qq_playlist = fetch_qq_playlist
        self.fetch_artist = fetch_artist_songs
        # Supplied by the service from the settings; on its own a letter keeps to the three QQ charts.
        self.sources = lambda: {'charts': [f'qq:{i}' for i, _ in CHARTS], 'taste': False, 'playlists': [], 'count': 3}
        self.fetch_quote = fetch_hitokoto
        self.today = today or (lambda: date.today().isoformat())
        # Supplied by the desk: short postscripts for a day (pending commissions, anniversaries, …).
        self.context = lambda day: []
        self.favored = lambda: set()  # pressed songs: the old letter likes to bring one back
        self.geese = lambda day: None  # 鸿雁: a paragraph about the day's school notices, or None
        self._lock = threading.Lock()
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            self.letters = [l for l in data if isinstance(l, dict) and l.get('date')] if isinstance(data, list) else []
        except (OSError, ValueError):
            self.letters = []

    # ------------------------------------------------------------ public

    def list(self):
        with self._lock:
            return [dict(l) for l in self.letters]

    def get(self, day):
        with self._lock:
            return next((dict(l) for l in self.letters if l['date'] == day), None)

    def today_letter(self, library_roots=None):
        day = self.today()
        existing = self.get(day)
        if existing:
            return existing
        letter = self._compose(day, library_roots)
        with self._lock:
            if not any(l['date'] == day for l in self.letters):
                before = list(self.letters)
                self.letters.insert(0, letter)
                self._trim()
                try:
                    self._save()
                except OSError:
                    self.letters = before
                    raise
        return self.get(day)

    def update(self, day, **changes):
        """Change opened / starred. The new state is only reported once it has reached the disk."""
        with self._lock:
            for letter in self.letters:
                if letter['date'] == day:
                    before = dict(letter)
                    letter.update({k: v for k, v in changes.items() if k in ('opened', 'starred')})
                    try:
                        self._save()
                    except OSError as error:
                        letter.clear()
                        letter.update(before)
                        raise OSError(f'这封信的变化没能保存：{error.strerror or error}') from error
                    return dict(letter)
        raise LookupError('没有这一天的信')

    def _trim(self):
        """Starred letters are kept forever; only ordinary ones beyond the limit are let go, oldest first."""
        ordinary = [l for l in self.letters if not l.get('starred')]
        if len(ordinary) <= LETTER_LIMIT:
            return
        drop = {id(l) for l in ordinary[LETTER_LIMIT:]}
        self.letters = [l for l in self.letters if id(l) not in drop]

    # ------------------------------------------------------------ composing

    def _compose(self, day, library_roots=None):
        seed = int(day.replace('-', ''))
        rng = random.Random(seed)
        recent = self.letters[:60]
        # Scan first, so "songs you don't have yet" really leaves out what you own, even on a cold start.
        tracks = self.library.list()
        if not tracks and library_roots:
            tracks = self.library.scan(library_roots)
        quote = self._quote(rng, seed, recent)
        songs, chart, error, intro = self._new_songs(rng, seed, recent, tracks)
        old = self._old_letter(rng, recent, tracks)
        weekday = datetime.strptime(day, '%Y-%m-%d').weekday()
        try:
            notes = [str(n) for n in self.context(day) or [] if n][:4]
        except Exception:
            notes = []
        return {'date': day, 'weekday': f'星期{"一二三四五六日"[weekday]}', 'created': time.time(),
                'greeting': rng.choice(GREETINGS), 'closing': rng.choice(CLOSINGS),
                'quote': quote, 'songs': songs, 'chart': chart, 'songs_intro': intro, 'songs_error': error, 'old': old,
                'notes': notes, 'geese': self._geese(day), 'weekly': weekday == 6, 'opened': False, 'starred': False}

    def _geese(self, day):
        try:
            return self.geese(day)
        except Exception:
            return None

    def refresh_geese(self, day):
        """Notices can arrive after the letter was written: until it is opened, its 鸿雁 paragraph follows them."""
        fresh = self._geese(day)
        with self._lock:
            letter = next((l for l in self.letters if l['date'] == day), None)
            if not letter or letter.get('opened') or letter.get('geese') == fresh:
                return dict(letter) if letter else None
            before = letter.get('geese')
            letter['geese'] = fresh
            try:
                self._save()
            except OSError:
                letter['geese'] = before
            return dict(letter)

    def _quote(self, rng, seed, recent):
        if seed % 3 == 0:
            try:
                quote = self.fetch_quote()
                if quote:
                    return quote
            except Exception:
                pass
        used = {l.get('quote', {}).get('text') for l in self.letters[:len(self.quotes) - 1]}
        fresh = [q for q in self.quotes if q['text'] not in used] or self.quotes
        return dict(rng.choice(fresh))

    # ------------------------------------------------------------ new songs, from the ticked sources

    def _settings(self):
        try:
            src = dict(DEFAULT_SOURCES, **(self.sources() or {}))
        except Exception:
            src = dict(DEFAULT_SOURCES)
        src['count'] = max(1, min(5, int(src.get('count') or 3)))
        return src

    def _fetch_source(self, kind, ref, tracks, rng):
        """(songs, label, platform, artist) for one source."""
        if kind == 'chart':
            platform, _, cid = ref.partition(':')
            name = CHART_CATALOG.get(ref, '榜单')
            if platform == 'qq':
                return self.fetch_chart(int(cid))[0], name, 'qq', None
            return self.fetch_netease(cid)[1], name, 'netease', None
        if kind == 'playlist':
            platform, pid = parse_playlist_link(ref)
            name, songs = self.fetch_netease(pid) if platform == 'netease' else self.fetch_qq_playlist(pid)
            return songs, name, platform, None
        # Taste: one of the artists you listen to most (played or pressed).
        weight = {}
        for t in tracks:
            artist = re.split(r'\s*(?:/|,|、|&|;|，)\s*', t.get('artist') or '')[0].strip()
            if artist:
                weight[artist] = weight.get(artist, 0) + 1 + int((self.plays.data.get(t['id']) or {}).get('count', 0))
        top = sorted(weight, key=lambda a: -weight[a])[:8]
        if not top:
            return [], '', 'netease', None
        artist = rng.choice(top)
        return self.fetch_artist(artist), f'{artist}的歌', 'netease', artist

    def _new_songs(self, rng, seed, recent, tracks):
        src = self._settings()
        count = src['count']
        sources = [('chart', c) for c in src['charts'] if c in CHART_CATALOG]
        sources += [('playlist', p) for p in src['playlists'] if isinstance(p, str) and p.strip()]
        if src['taste'] and tracks:
            sources.append(('taste', None))
        if not sources:
            return [], '', '设置里还没有勾选新歌的来源', ''
        rng.shuffle(sources)
        owned = {song_signature(t.get('title'), t.get('artist')) for t in tracks}
        sent_before = {s.get('id') for l in recent for s in l.get('songs') or []}
        # Two sources a day at most, so the letter has a little variety but still reads like one choice.
        share = count if len(sources) == 1 else (count + 1) // 2
        picks, used, errors = [], [], []
        for kind, ref in sources:
            if len(picks) >= count or len(used) >= 2:
                break
            try:
                songs, label, platform, artist = self._fetch_source(kind, ref, tracks, rng)
            except Exception as error:
                errors.append(f'{type(error).__name__}')
                continue
            taken = {song_signature(s['name'], s['artist']) for s in picks}
            fresh = [s for s in songs if s.get('id') and song_signature(s['name'], s['artist']) not in owned | taken]
            pool = [s for s in fresh if s['id'] not in sent_before] or fresh
            if not pool:
                continue
            want = min(count - len(picks), share if len(used) == 0 else count - len(picks))
            chosen = rng.sample(pool, min(want, len(pool)))
            picks += [dict(s, platform=s.get('platform') or platform, chart=label, source=kind) for s in chosen]
            used.append({'kind': kind, 'label': label, 'platform': platform, 'artist': artist})
        if not picks:
            return [], '', (f'新歌的来源暂时取不到：{errors[0]}' if errors else ''), ''
        return picks, '、'.join(u['label'] for u in used), '', self._intro(used, len(picks))

    @staticmethod
    def _intro(used, n):
        parts = []
        for u in used:
            if u['kind'] == 'taste':
                parts.append(f'顺着你常听的{u["artist"]}')
            elif u['kind'] == 'playlist':
                parts.append(f'从你留下的歌单「{u["label"]}」里')
            else:
                name = PLATFORM_NAME.get(u['platform'], '')
                parts.append(f'从{" " if name[:1].isascii() else ""}{name}「{u["label"]}」里')
        number = '一二三四五'[n - 1]
        return f'今天{"，又".join(parts)}，替你挑了{number}首书信匣里还没有的歌：'

    def _old_letter(self, rng, recent, tracks):
        if not tracks:
            return None
        featured = {(l.get('old') or {}).get('id') for l in recent}
        cutoff = time.time() - OLD_AFTER_DAYS * 86400
        candidates = [t for t in tracks if self.plays.last(t['id']) < cutoff and t['id'] not in featured]
        if not candidates:
            candidates = [t for t in tracks if t['id'] not in featured] or tracks
        candidates.sort(key=lambda t: (self.plays.last(t['id']), t.get('mtime', 0)))
        try:
            favored = self.favored() or set()
        except Exception:
            favored = set()
        pressed = [t for t in candidates if t['id'] in favored]
        # Every other day, if one of your pressed songs has gone quiet, that is the one she brings back.
        if pressed and rng.random() < 0.5:
            choice = rng.choice(pressed[:5])
        else:
            choice = rng.choice(candidates[:max(5, len(candidates) // 4)])
        last = self.plays.last(choice['id'])
        return {'id': choice['id'], 'title': choice['title'], 'artist': choice['artist'], 'album': choice['album'],
                'has_cover': choice.get('has_cover', False), 'last_played': last, 'added': choice.get('mtime', 0),
                'pressed': choice['id'] in favored}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(self.path, self.letters)
