"""信札与压花：收藏的歌（压花）和自己扎的歌单（信札）。

和书桌共用 desk.db，所以每天的备份里自然带着它们。
- 曲目按曲库 id 记录，同时存下歌名、歌手、专辑。文件挪动或改名后 id 会变，就按「歌名 + 歌手」重新认回来。
- 从在线歌单「抄成信札」的歌还没下载时没有 id，是「在路上」的信；寄进书信匣后自动认领。
- 拆散的信札先进回收站，30 天后才清除。
"""
import re
import uuid

from violet_desk import Conflict, TRASH_DAYS, iso, parse_day

SCHEMA = """
CREATE TABLE IF NOT EXISTS pressed (
    track_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '', artist TEXT NOT NULL DEFAULT '',
    album TEXT NOT NULL DEFAULT '', has_cover INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
    day TEXT NOT NULL, pressed_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS bundles (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, epigraph TEXT NOT NULL DEFAULT '', ribbon TEXT NOT NULL DEFAULT 'violet',
    position REAL NOT NULL DEFAULT 0, created REAL, updated REAL, revision INTEGER NOT NULL DEFAULT 1, deleted_at REAL);
CREATE TABLE IF NOT EXISTS bundle_letters (
    id TEXT PRIMARY KEY, bundle_id TEXT NOT NULL, track_id TEXT, title TEXT NOT NULL DEFAULT '',
    artist TEXT NOT NULL DEFAULT '', album TEXT NOT NULL DEFAULT '', has_cover INTEGER NOT NULL DEFAULT 0,
    position REAL NOT NULL, added REAL NOT NULL);
CREATE INDEX IF NOT EXISTS bundle_letters_bundle ON bundle_letters (bundle_id, position);
"""
RIBBONS = ('violet', 'wine', 'prussian', 'moss', 'gold', 'rose')
MAX_LETTERS = 2000


def song_key(title, artist):
    """Loose identity of a song: case, spaces, punctuation and featured artists do not matter."""
    first = re.split(r'\s*(?:/|,|、|&|;|，|feat\.?|ft\.)\s*', (artist or '').casefold())[0]
    return _squash(title) + '|' + _squash(first)


def _squash(text):
    return re.sub(r'[\s\W_]+', '', (text or '').casefold())


def _text(value, limit, field):
    value = str(value or '').strip()
    if len(value) > limit:
        raise ValueError(f'{field}最多 {limit} 个字')
    return value


class Shelf:
    def __init__(self, desk):
        self.desk = desk
        with desk._lock:
            desk.db.executescript(SCHEMA)
        self.purge_trash()

    # ------------------------------------------------------------ helpers

    def _rows(self, sql, args=()):
        return self.desk._rows(sql, args)

    def _row(self, sql, args=()):
        return self.desk._row(sql, args)

    def _tx(self):
        return self.desk._tx()

    def _now(self):
        return self.desk.clock()

    def purge_trash(self):
        cutoff = self._now() - TRASH_DAYS * 86400
        with self._tx() as db:
            gone = [r[0] for r in db.execute('SELECT id FROM bundles WHERE deleted_at IS NOT NULL AND deleted_at < ?',
                                             (cutoff,)).fetchall()]
            for bid in gone:
                db.execute('DELETE FROM bundle_letters WHERE bundle_id = ?', (bid,))
                db.execute('DELETE FROM bundles WHERE id = ?', (bid,))

    @staticmethod
    def _index(tracks):
        by_key = {}
        for track in tracks.values():
            by_key.setdefault(song_key(track.get('title'), track.get('artist')), track['id'])
        return by_key

    def _resolve(self, rows, tracks, table):
        """Attach the library track to each row; re-link rows whose file moved; mark the rest lost or pending."""
        index = None
        out = []
        relinks = []
        for row in rows:
            track = tracks.get(row['track_id']) if row['track_id'] else None
            if not track:
                index = index if index is not None else self._index(tracks)
                found = index.get(song_key(row['title'], row['artist']))
                if found:
                    track = tracks[found]
                    relinks.append((row, found))
            state = 'here' if track else ('lost' if row['track_id'] else 'pending')
            item = dict(row, state=state, track=track)
            if track:
                item.update(track_id=track['id'], has_cover=bool(track.get('has_cover')))
            out.append(item)
        if relinks:
            with self._tx() as db:
                for row, new_id in relinks:
                    if table == 'pressed':
                        taken = db.execute('SELECT 1 FROM pressed WHERE track_id = ?', (new_id,)).fetchone()
                        if taken:
                            db.execute('DELETE FROM pressed WHERE track_id = ?', (row['track_id'],))
                        else:
                            db.execute('UPDATE pressed SET track_id = ? WHERE track_id = ?', (new_id, row['track_id']))
                    else:
                        db.execute('UPDATE bundle_letters SET track_id = ? WHERE id = ?', (new_id, row['id']))
        return out

    @staticmethod
    def _song(track):
        if not isinstance(track, dict):
            raise ValueError('缺少歌曲信息')
        title = str(track.get('title') or '').strip()[:200]
        if not title:
            raise ValueError('缺少歌名')
        # A library track carries `id`; a row coming back (undo) carries `track_id`, which may be empty when pending.
        raw_id = track.get('track_id') if 'track_id' in track else track.get('id')
        return {'track_id': str(raw_id or '').strip()[:40] or None,
                'title': title, 'artist': str(track.get('artist') or '').strip()[:200],
                'album': str(track.get('album') or '').strip()[:200], 'has_cover': 1 if track.get('has_cover') else 0}

    # ------------------------------------------------------------ 压花 (favourites)

    def pressed_ids(self):
        return [r['track_id'] for r in self._rows('SELECT track_id FROM pressed')]

    def pressed(self, tracks):
        rows = self._rows('SELECT * FROM pressed ORDER BY pressed_at DESC')
        return self._resolve(rows, tracks, 'pressed')

    def press(self, track, note=None):
        song = self._song(track)
        if not song['track_id']:
            raise ValueError('只有书信匣里的歌才能压花')
        now = self._now()
        with self._tx() as db:
            db.execute("""INSERT INTO pressed (track_id, title, artist, album, has_cover, note, day, pressed_at)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                          ON CONFLICT (track_id) DO UPDATE SET note = COALESCE(?, note)""",
                       (song['track_id'], song['title'], song['artist'], song['album'], song['has_cover'],
                        _text(note, 120, '压花笺'), iso(self.desk.today()), now,
                        None if note is None else _text(note, 120, '压花笺')))
        return self._row('SELECT * FROM pressed WHERE track_id = ?', (song['track_id'],))

    def unpress(self, track_id):
        with self._tx() as db:
            row = db.execute('SELECT * FROM pressed WHERE track_id = ?', (track_id,)).fetchone()
            db.execute('DELETE FROM pressed WHERE track_id = ?', (track_id,))
        return dict(row) if row else None

    def holding(self, track_id):
        """Names of the bundles a library song is tucked into."""
        rows = self._rows("""SELECT DISTINCT b.name FROM bundle_letters l JOIN bundles b ON b.id = l.bundle_id
                             WHERE l.track_id = ? AND b.deleted_at IS NULL ORDER BY b.position""", (track_id,))
        return [r['name'] for r in rows]

    def forget_tracks(self, ids, tracks):
        """Songs sent back: their flowers and bundle letters follow another copy of the same song if one is left,
        otherwise they are taken down."""
        index = self._index(tracks)
        with self._tx() as db:
            for tid in ids:
                row = db.execute('SELECT title, artist FROM pressed WHERE track_id = ?', (tid,)).fetchone()
                letters = db.execute('SELECT id, bundle_id, title, artist FROM bundle_letters WHERE track_id = ?',
                                     (tid,)).fetchall()
                if row:
                    other = index.get(song_key(row['title'], row['artist']))
                    taken = other and db.execute('SELECT 1 FROM pressed WHERE track_id = ?', (other,)).fetchone()
                    if other and not taken:
                        db.execute('UPDATE pressed SET track_id = ? WHERE track_id = ?', (other, tid))
                    else:
                        db.execute('DELETE FROM pressed WHERE track_id = ?', (tid,))
                for letter in letters:
                    other = index.get(song_key(letter['title'], letter['artist']))
                    twin = other and db.execute('SELECT 1 FROM bundle_letters WHERE bundle_id = ? AND track_id = ?',
                                                (letter['bundle_id'], other)).fetchone()
                    if other and not twin:
                        db.execute('UPDATE bundle_letters SET track_id = ? WHERE id = ?', (other, letter['id']))
                    else:
                        db.execute('DELETE FROM bundle_letters WHERE id = ?', (letter['id'],))

    def pressed_on(self, day):
        return self._rows('SELECT * FROM pressed WHERE day = ? ORDER BY pressed_at', (iso(parse_day(day)),))

    def pressed_days(self, start, end):
        rows = self._rows('SELECT day, COUNT(*) AS n FROM pressed WHERE day >= ? AND day <= ? GROUP BY day',
                          (iso(start), iso(end)))
        return {r['day']: r['n'] for r in rows}

    # ------------------------------------------------------------ 信札 (playlists)

    def _bundle_row(self, bid):
        row = self._row('SELECT * FROM bundles WHERE id = ? AND deleted_at IS NULL', (bid,))
        if not row:
            raise LookupError('这束信札不存在或已拆散')
        return row

    def _letters(self, bid, tracks):
        rows = self._rows('SELECT * FROM bundle_letters WHERE bundle_id = ? ORDER BY position, added', (bid,))
        return self._resolve(rows, tracks, 'bundle_letters')

    def _summary(self, row, letters):
        here = [l for l in letters if l['state'] == 'here']
        covers = [l['track_id'] for l in here if l['has_cover']][:3]
        return dict(row, count=len(letters), here=len(here), pending=sum(l['state'] == 'pending' for l in letters),
                    lost=sum(l['state'] == 'lost' for l in letters), covers=covers,
                    duration=sum(l['track'].get('duration') or 0 for l in here))

    def bundles(self, tracks):
        rows = self._rows('SELECT * FROM bundles WHERE deleted_at IS NULL ORDER BY position, created')
        return [self._summary(r, self._letters(r['id'], tracks)) for r in rows]

    def bundle(self, bid, tracks):
        row = self._bundle_row(bid)
        letters = self._letters(bid, tracks)
        return dict(self._summary(row, letters), letters=letters)

    def _fields(self, data, partial):
        out = {}
        if not partial or 'name' in data:
            out['name'] = _text(data.get('name'), 40, '信札的名字')
            if not out['name']:
                raise ValueError('给这束信札起个名字吧')
        if not partial or 'epigraph' in data:
            out['epigraph'] = _text(data.get('epigraph'), 80, '题记')
        if not partial or 'ribbon' in data:
            ribbon = data.get('ribbon') or 'violet'
            if ribbon not in RIBBONS:
                raise ValueError('没有这种缎带')
            out['ribbon'] = ribbon
        return out

    def create_bundle(self, data, tracks=None):
        fields = self._fields(data or {}, partial=False)
        now = self._now()
        bid = uuid.uuid4().hex[:12]
        with self._tx() as db:
            last = db.execute('SELECT MAX(position) FROM bundles WHERE deleted_at IS NULL').fetchone()[0]
            db.execute("""INSERT INTO bundles (id, name, epigraph, ribbon, position, created, updated)
                          VALUES (?, ?, ?, ?, ?, ?, ?)""",
                       (bid, fields['name'], fields['epigraph'], fields['ribbon'], (last or 0) + 1, now, now))
        return self.bundle(bid, tracks or {})

    def update_bundle(self, bid, data, tracks=None):
        row = self._bundle_row(bid)
        revision = data.get('revision')
        if revision is not None and int(revision) != row['revision']:
            raise Conflict(self.bundle(bid, tracks or {}))
        fields = self._fields(data, partial=True)
        if fields:
            sets = ', '.join(f'{k} = ?' for k in fields)
            with self._tx() as db:
                db.execute(f'UPDATE bundles SET {sets}, updated = ?, revision = revision + 1 WHERE id = ?',
                           (*fields.values(), self._now(), bid))
        return self.bundle(bid, tracks or {})

    def delete_bundle(self, bid, restore=False):
        with self._tx() as db:
            changed = db.execute('UPDATE bundles SET deleted_at = ?, revision = revision + 1 WHERE id = ?',
                                 (None if restore else self._now(), bid)).rowcount
        if not changed:
            raise LookupError('这束信札不存在')

    def add(self, bid, songs, tracks=None):
        """Tuck songs into a bundle; a song already there is not added twice."""
        self._bundle_row(bid)
        if not isinstance(songs, list) or not songs:
            raise ValueError('没有要夹进去的歌')
        tracks = tracks or {}
        added = duplicates = 0
        now = self._now()
        with self._tx() as db:
            existing = db.execute('SELECT track_id, title, artist FROM bundle_letters WHERE bundle_id = ?',
                                  (bid,)).fetchall()
            if len(existing) + len(songs) > MAX_LETTERS:
                raise ValueError(f'一束信札最多 {MAX_LETTERS} 封')
            ids = {r['track_id'] for r in existing if r['track_id']}
            keys = {song_key(r['title'], r['artist']) for r in existing}
            last = db.execute('SELECT MAX(position) FROM bundle_letters WHERE bundle_id = ?', (bid,)).fetchone()[0] or 0
            for raw in songs:
                song = self._song(raw)
                key = song_key(song['title'], song['artist'])
                if (song['track_id'] and song['track_id'] in ids) or key in keys:
                    duplicates += 1
                    continue
                position = raw.get('position')
                if not isinstance(position, (int, float)):
                    last += 1
                    position = last
                db.execute("""INSERT INTO bundle_letters (id, bundle_id, track_id, title, artist, album, has_cover,
                              position, added) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                           (uuid.uuid4().hex[:12], bid, song['track_id'], song['title'], song['artist'], song['album'],
                            song['has_cover'], position, now))
                ids.add(song['track_id'])
                keys.add(key)
                added += 1
            db.execute('UPDATE bundles SET updated = ?, revision = revision + 1 WHERE id = ?', (now, bid))
        return {'added': added, 'duplicates': duplicates, 'bundle': self.bundle(bid, tracks)}

    def remove(self, bid, letter_ids, tracks=None):
        """Take letters out; the removed rows come back so the page can offer to put them back."""
        self._bundle_row(bid)
        letter_ids = [str(i) for i in letter_ids or []][:MAX_LETTERS]
        removed = []
        with self._tx() as db:
            for lid in letter_ids:
                row = db.execute('SELECT * FROM bundle_letters WHERE id = ? AND bundle_id = ?', (lid, bid)).fetchone()
                if row:
                    removed.append(dict(row))
                    db.execute('DELETE FROM bundle_letters WHERE id = ?', (lid,))
            db.execute('UPDATE bundles SET updated = ?, revision = revision + 1 WHERE id = ?', (self._now(), bid))
        return {'removed': removed, 'bundle': self.bundle(bid, tracks or {})}

    def reorder(self, bid, letter_ids, tracks=None):
        self._bundle_row(bid)
        with self._tx() as db:
            for position, lid in enumerate(letter_ids or [], start=1):
                db.execute('UPDATE bundle_letters SET position = ? WHERE id = ? AND bundle_id = ?', (position, lid, bid))
            db.execute('UPDATE bundles SET updated = ?, revision = revision + 1 WHERE id = ?', (self._now(), bid))
        return self.bundle(bid, tracks or {})

    def memberships(self, track_id):
        """Which bundles a track is tucked into (for the 夹进信札 menu)."""
        return [r['bundle_id'] for r in self._rows(
            """SELECT DISTINCT l.bundle_id FROM bundle_letters l JOIN bundles b ON b.id = l.bundle_id
               WHERE b.deleted_at IS NULL AND l.track_id = ?""", (track_id,))]

    def all_memberships(self):
        rows = self._rows("""SELECT l.track_id, l.bundle_id FROM bundle_letters l JOIN bundles b ON b.id = l.bundle_id
                             WHERE b.deleted_at IS NULL AND l.track_id IS NOT NULL""")
        out = {}
        for r in rows:
            out.setdefault(r['track_id'], []).append(r['bundle_id'])
        return out
