"""书桌：委托（待办）、约定（日程）与纪念日、回信（日记）、聆听记录、代笔时间与每周封存。

全部保存在用户数据目录的 desk.db（SQLite，标准库自带）。
- 每条可编辑的记录带 revision：拿旧版本保存会得到 Conflict，界面据此提示，而不是悄悄覆盖。
- 删除先放进回收站（deleted_at），30 天后才真正清除。
- 重复委托在完成时生成下一份；撤销完成会收回尚未动过的下一份。
"""
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid

import violet_almanac as almanac
from violet_core import DATA_DIR, clean_stationery

DESK_FILE = DATA_DIR / 'desk.db'
TRASH_DAYS = 30
MOODS = ('sunny', 'warm', 'calm', 'tired', 'rainy', 'tangled', 'missing', 'fired')
WEATHERS = ('clear', 'cloudy', 'overcast', 'rain', 'snow', 'wind', 'fog', 'storm')
FREQS = ('daily', 'weekly', 'monthly', 'yearly')
REMIND_GRACE = 12 * 3600  # a reminder missed while Violet was closed is still delivered within this window

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS commissions (
    id TEXT PRIMARY KEY, number INTEGER, title TEXT NOT NULL, client TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open', due_date TEXT, due_time TEXT,
    remind INTEGER, repeat TEXT, steps TEXT NOT NULL DEFAULT '[]', focus_seconds INTEGER NOT NULL DEFAULT 0,
    series TEXT, spawned TEXT, created REAL, updated REAL, completed_at REAL, reminded_for TEXT,
    deleted_at REAL, revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'appointment', title TEXT NOT NULL,
    place TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', date TEXT NOT NULL, start TEXT, end TEXT,
    remind INTEGER, lunar INTEGER NOT NULL DEFAULT 0, lunar_month INTEGER, lunar_day INTEGER,
    reminded_for TEXT, created REAL, updated REAL, deleted_at REAL, revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS replies (
    id TEXT PRIMARY KEY, date TEXT NOT NULL, recipient TEXT NOT NULL DEFAULT 'violet', deliver_on TEXT,
    body TEXT NOT NULL DEFAULT '', mood TEXT, weather TEXT, song TEXT, photos TEXT NOT NULL DEFAULT '[]',
    attach_commissions INTEGER NOT NULL DEFAULT 1, commissions TEXT NOT NULL DEFAULT '[]', sealed_at REAL,
    opened_at REAL, starred INTEGER NOT NULL DEFAULT 0, created REAL, updated REAL, deleted_at REAL,
    revision INTEGER NOT NULL DEFAULT 1, stationery TEXT);
CREATE TABLE IF NOT EXISTS listens (
    day TEXT NOT NULL, track_id TEXT NOT NULL, title TEXT, artist TEXT, album TEXT, has_cover INTEGER,
    count INTEGER NOT NULL DEFAULT 0, last REAL, PRIMARY KEY (day, track_id));
CREATE TABLE IF NOT EXISTS focus (
    id TEXT PRIMARY KEY, commission_id TEXT, title TEXT, day TEXT NOT NULL, started REAL, seconds INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS weekly (
    week TEXT PRIMARY KEY, start TEXT, end TEXT, summary TEXT, note TEXT NOT NULL DEFAULT '', sealed_at REAL,
    revision INTEGER NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS commissions_due ON commissions (due_date);
CREATE INDEX IF NOT EXISTS appointments_date ON appointments (date);
CREATE INDEX IF NOT EXISTS replies_date ON replies (date);
"""


class Conflict(Exception):
    """Saved from an older revision; carries the current record."""

    def __init__(self, current):
        super().__init__('这条记录已经在别处改过了，已载入最新版本')
        self.current = current


def new_id():
    return uuid.uuid4().hex[:12]


def iso(day):
    return day.isoformat() if isinstance(day, date) else str(day)


def parse_day(value, field='日期'):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        raise ValueError(f'{field}格式不对，应为 YYYY-MM-DD') from None


def parse_time(value, field='时间'):
    if value in (None, ''):
        return None
    try:
        return datetime.strptime(str(value), '%H:%M').strftime('%H:%M')
    except ValueError:
        raise ValueError(f'{field}格式不对，应为 HH:MM') from None


def iso_week(day):
    year, week, _ = day.isocalendar()
    return f'{year}-W{week:02d}'


def week_bounds(week):
    try:
        year, number = week.split('-W')
        start = date.fromisocalendar(int(year), int(number), 1)
    except (ValueError, AttributeError):
        raise ValueError('周的格式应为 YYYY-Www') from None
    return start, start + timedelta(days=6)


def clean_repeat(value):
    if not value:
        return None
    if not isinstance(value, dict) or value.get('freq') not in FREQS:
        raise ValueError('重复规则不正确')
    interval = max(1, min(int(value.get('interval') or 1), 30))
    weekdays = sorted({int(d) for d in value.get('weekdays') or [] if str(d).isdigit() and 0 <= int(d) <= 6})
    return {'freq': value['freq'], 'interval': interval, 'weekdays': weekdays if value['freq'] == 'weekly' else []}


def next_occurrence(current, repeat):
    """The date after `current` for a repeat rule."""
    freq, interval = repeat['freq'], repeat.get('interval', 1)
    if freq == 'daily':
        return current + timedelta(days=interval)
    if freq == 'weekly':
        days = repeat.get('weekdays') or [current.weekday()]
        for step in range(1, 8):
            candidate = current + timedelta(days=step)
            if candidate.weekday() in days:
                # Crossing into a new week skips the weeks the interval leaves out.
                if candidate.weekday() <= current.weekday():
                    candidate += timedelta(weeks=interval - 1)
                return candidate
    if freq == 'monthly':
        month = current.month - 1 + interval
        year, month = current.year + month // 12, month % 12 + 1
        for day in range(current.day, 27, -1):
            try:
                return date(year, month, day)
            except ValueError:
                continue
        return date(year, month, min(current.day, 28))
    if freq == 'yearly':
        try:
            return current.replace(year=current.year + interval)
        except ValueError:  # 29 February
            return date(current.year + interval, 2, 28)
    raise ValueError('未知的重复频率')


def clean_steps(steps):
    out = []
    for step in steps or []:
        if isinstance(step, str):
            step = {'text': step}
        if not isinstance(step, dict) or not str(step.get('text', '')).strip():
            continue
        out.append({'id': str(step.get('id') or new_id())[:16], 'text': str(step['text']).strip()[:200],
                    'done': bool(step.get('done'))})
    return out[:50]


class Desk:
    def __init__(self, path=None, today=None, clock=None):
        self.path = Path(path or DESK_FILE)
        self.today = today or date.today
        self.clock = clock or time.time
        self._lock = threading.RLock()
        self.db = None
        self.open()

    # ------------------------------------------------------------ connection

    def open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=DELETE')
        db.execute('PRAGMA synchronous=FULL')
        db.executescript(SCHEMA)
        # Columns added after the first release.
        columns = {r['name'] for r in db.execute('PRAGMA table_info(replies)')}
        if 'stationery' not in columns:
            db.execute('ALTER TABLE replies ADD COLUMN stationery TEXT')
        db.execute("INSERT OR IGNORE INTO meta VALUES ('schema', '1')")
        self.db = db
        self.purge_trash()

    def close(self):
        with self._lock:
            if self.db is not None:
                self.db.close()
                self.db = None

    def backup_to(self, target):
        """A consistent copy of the live database (SQLite online backup)."""
        with self._lock:
            out = sqlite3.connect(str(target))
            try:
                self.db.backup(out)
            finally:
                out.close()

    def _tx(self):
        return _Transaction(self)

    def _rows(self, sql, args=()):
        with self._lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def _row(self, sql, args=()):
        rows = self._rows(sql, args)
        return rows[0] if rows else None

    def purge_trash(self):
        cutoff = self.clock() - TRASH_DAYS * 86400
        with self._tx() as db:
            for table in ('commissions', 'appointments', 'replies'):
                db.execute(f'DELETE FROM {table} WHERE deleted_at IS NOT NULL AND deleted_at < ?', (cutoff,))

    def _check_revision(self, table, record_id, revision, loader):
        row = self._row(f'SELECT revision, deleted_at FROM {table} WHERE id = ?', (record_id,))
        if not row or row['deleted_at']:
            raise LookupError('这条记录不存在或已删除')
        if revision is not None and int(revision) != row['revision']:
            raise Conflict(loader(record_id))
        return row['revision']

    # ------------------------------------------------------------ commissions

    @staticmethod
    def _commission(row):
        if not row:
            return None
        row = dict(row)
        row['steps'] = json.loads(row['steps'] or '[]')
        row['repeat'] = json.loads(row['repeat']) if row['repeat'] else None
        return row

    def commission(self, cid):
        return self._commission(self._row('SELECT * FROM commissions WHERE id = ?', (cid,)))

    def commissions(self, include_done=True):
        sql = 'SELECT * FROM commissions WHERE deleted_at IS NULL'
        if not include_done:
            sql += " AND status = 'open'"
        rows = self._rows(sql + ' ORDER BY status, due_date IS NULL, due_date, due_time IS NULL, due_time, number')
        return [self._commission(r) for r in rows]

    def clients(self):
        rows = self._rows("""SELECT client, SUM(status = 'open') AS open, COUNT(*) AS total FROM commissions
                             WHERE deleted_at IS NULL AND client != '' GROUP BY client ORDER BY MAX(updated) DESC""")
        return rows

    def _commission_fields(self, data, partial):
        out = {}
        if 'title' in data or not partial:
            title = str(data.get('title') or '').strip()
            if not title:
                raise ValueError('委托需要一个标题')
            out['title'] = title[:200]
        if 'client' in data:
            out['client'] = str(data.get('client') or '').strip()[:40]
        if 'note' in data:
            out['note'] = str(data.get('note') or '')[:5000]
        if 'due_date' in data:
            out['due_date'] = iso(parse_day(data['due_date'], '期限')) if data['due_date'] else None
        if 'due_time' in data:
            out['due_time'] = parse_time(data['due_time'], '期限时间')
        if 'remind' in data:
            out['remind'] = None if data['remind'] in (None, '') else max(0, min(int(data['remind']), 7 * 1440))
        if 'repeat' in data:
            repeat = clean_repeat(data['repeat'])
            out['repeat'] = json.dumps(repeat) if repeat else None
        if 'steps' in data:
            out['steps'] = json.dumps(clean_steps(data['steps']), ensure_ascii=False)
        return out

    def create_commission(self, data):
        fields = self._commission_fields(data, partial=False)
        fields.setdefault('client', '')
        if fields.get('repeat') and not fields.get('due_date'):
            fields['due_date'] = iso(self.today())
        now = self.clock()
        with self._tx() as db:
            number = self._next_number(db)
            cid = new_id()
            fields.update(id=cid, number=number, created=now, updated=now, series=data.get('series') or cid)
            columns = ', '.join(fields)
            db.execute(f'INSERT INTO commissions ({columns}) VALUES ({", ".join("?" * len(fields))})',
                       tuple(fields.values()))
        return self.commission(cid)

    def update_commission(self, cid, data):
        fields = self._commission_fields(data, partial=True)
        with self._lock:
            self._check_revision('commissions', cid, data.get('revision'), self.commission)
            if 'due_date' in fields or 'due_time' in fields or 'remind' in fields:
                fields['reminded_for'] = None
            if fields:
                fields['updated'] = self.clock()
                sets = ', '.join(f'{k} = ?' for k in fields)
                with self._tx() as db:
                    db.execute(f'UPDATE commissions SET {sets}, revision = revision + 1 WHERE id = ?',
                               (*fields.values(), cid))
        return self.commission(cid)

    def complete_commission(self, cid, done=True):
        """Mark done (spawning the next one of a series) or undo. Returns (commission, spawned or None)."""
        with self._lock:
            item = self.commission(cid)
            if not item or item['deleted_at']:
                raise LookupError('这份委托不存在')
            now = self.clock()
            spawned = None
            with self._tx() as db:
                if done and item['status'] != 'done':
                    db.execute("""UPDATE commissions SET status = 'done', completed_at = ?, updated = ?,
                                  revision = revision + 1 WHERE id = ?""", (now, now, cid))
                    if item['repeat']:
                        spawned = self._spawn_next(db, item)
                elif not done and item['status'] == 'done':
                    db.execute("""UPDATE commissions SET status = 'open', completed_at = NULL, updated = ?,
                                  revision = revision + 1, spawned = NULL WHERE id = ?""", (now, cid))
                    if item['spawned']:
                        # Take back the next instance only if nobody touched it yet.
                        db.execute("""DELETE FROM commissions WHERE id = ? AND revision = 1 AND status = 'open'""",
                                   (item['spawned'],))
        return self.commission(cid), (self.commission(spawned) if spawned else None)

    @staticmethod
    def _next_number(db):
        row = db.execute("SELECT value FROM meta WHERE key = 'commission_seq'").fetchone()
        number = int(row[0] if row else 0) + 1
        db.execute("INSERT OR REPLACE INTO meta VALUES ('commission_seq', ?)", (str(number),))
        return number

    def _spawn_next(self, db, item):
        today = self.today()
        due = parse_day(item['due_date']) if item['due_date'] else today
        following = next_occurrence(due, item['repeat'])
        while following < today:
            following = next_occurrence(following, item['repeat'])
        number = self._next_number(db)
        nid, now = new_id(), self.clock()
        steps = [dict(s, done=False) for s in item['steps']]
        db.execute("""INSERT INTO commissions (id, number, title, client, note, due_date, due_time, remind, repeat,
                      steps, series, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   (nid, number, item['title'], item['client'], item['note'], iso(following), item['due_time'],
                    item['remind'], json.dumps(item['repeat']), json.dumps(steps, ensure_ascii=False),
                    item['series'] or item['id'], now, now))
        db.execute('UPDATE commissions SET spawned = ? WHERE id = ?', (nid, item['id']))
        return nid

    def delete(self, table, record_id, restore=False):
        if table not in ('commissions', 'appointments', 'replies'):
            raise ValueError('未知的记录类型')
        with self._tx() as db:
            changed = db.execute(f'UPDATE {table} SET deleted_at = ?, revision = revision + 1 WHERE id = ?',
                                 (None if restore else self.clock(), record_id)).rowcount
        if not changed:
            raise LookupError('这条记录不存在')

    def add_focus(self, cid, seconds, started=None):
        seconds = max(0, min(int(seconds), 12 * 3600))
        item = self.commission(cid) if cid else None
        if cid and not item:
            raise LookupError('这份委托不存在')
        with self._tx() as db:
            db.execute('INSERT INTO focus VALUES (?, ?, ?, ?, ?, ?)',
                       (new_id(), cid, item['title'] if item else '', iso(self.today()), started or self.clock(),
                        seconds))
            if item:
                db.execute('UPDATE commissions SET focus_seconds = focus_seconds + ?, updated = ? WHERE id = ?',
                           (seconds, self.clock(), cid))
        return self.commission(cid) if cid else None

    # ------------------------------------------------------------ appointments and anniversaries

    def appointment(self, aid):
        return self._row('SELECT * FROM appointments WHERE id = ?', (aid,))

    def _appointment_fields(self, data, partial):
        out = {}
        if 'title' in data or not partial:
            title = str(data.get('title') or '').strip()
            if not title:
                raise ValueError('需要写下这是什么约定')
            out['title'] = title[:200]
        if 'kind' in data or not partial:
            kind = data.get('kind') or 'appointment'
            if kind not in ('appointment', 'anniversary'):
                raise ValueError('未知的约定类型')
            out['kind'] = kind
        if 'date' in data or not partial:
            out['date'] = iso(parse_day(data.get('date')))
        for name in ('place', 'note'):
            if name in data:
                out[name] = str(data.get(name) or '')[:2000]
        for name in ('start', 'end'):
            if name in data:
                out[name] = parse_time(data[name])
        if 'remind' in data:
            out['remind'] = None if data['remind'] in (None, '') else max(0, min(int(data['remind']), 7 * 1440))
        if 'lunar' in data:
            out['lunar'] = 1 if data['lunar'] else 0
        if out.get('lunar') or ('date' in out and data.get('lunar')):
            info = almanac.lunar(out.get('date') or data.get('date'))
            if not info:
                raise ValueError('这一天超出了农历换算范围')
            out['lunar_month'], out['lunar_day'] = info['month'], info['day']
        return out

    def create_appointment(self, data):
        fields = self._appointment_fields(data, partial=False)
        now = self.clock()
        fields.update(id=new_id(), created=now, updated=now)
        with self._tx() as db:
            db.execute(f'INSERT INTO appointments ({", ".join(fields)}) VALUES ({", ".join("?" * len(fields))})',
                       tuple(fields.values()))
        return self.appointment(fields['id'])

    def update_appointment(self, aid, data):
        with self._lock:
            self._check_revision('appointments', aid, data.get('revision'), self.appointment)
            current = self.appointment(aid)
            merged = dict(data)
            if 'lunar' not in merged and 'date' in merged:
                merged['lunar'] = bool(current['lunar'])
            fields = self._appointment_fields(merged, partial=True)
            if {'date', 'start', 'remind'} & set(fields):
                fields['reminded_for'] = None
            if fields:
                fields['updated'] = self.clock()
                sets = ', '.join(f'{k} = ?' for k in fields)
                with self._tx() as db:
                    db.execute(f'UPDATE appointments SET {sets}, revision = revision + 1 WHERE id = ?',
                               (*fields.values(), aid))
        return self.appointment(aid)

    def occurrences(self, start, end):
        """Appointments in [start, end], with anniversaries repeated every year (by lunar date if asked)."""
        start, end = parse_day(start), parse_day(end)
        out = []
        for row in self._rows("SELECT * FROM appointments WHERE deleted_at IS NULL AND kind = 'appointment' "
                              'AND date BETWEEN ? AND ? ORDER BY date, start IS NOT NULL, start', (iso(start), iso(end))):
            out.append(dict(row, on=row['date']))
        for row in self._rows("SELECT * FROM appointments WHERE deleted_at IS NULL AND kind = 'anniversary'"):
            origin = parse_day(row['date'])
            for year in range(start.year - 1, end.year + 1):
                if row['lunar'] and row['lunar_month']:
                    on = almanac.lunar_to_solar(year, row['lunar_month'], row['lunar_day']) or \
                        almanac.lunar_to_solar(year, row['lunar_month'], row['lunar_day'] - 1)
                else:
                    try:
                        on = origin.replace(year=year)
                    except ValueError:
                        on = date(year, 2, 28)
                if on and start <= on <= end and on >= origin:
                    years = (almanac.lunar(on) or {}).get('year', on.year) - (almanac.lunar(origin) or {}).get(
                        'year', origin.year) if row['lunar'] else on.year - origin.year
                    out.append(dict(row, on=iso(on), years=years))
        out.sort(key=lambda r: (r['on'], r['kind'] != 'anniversary', r['start'] or ''))
        return out

    # ------------------------------------------------------------ replies (the user's letters)

    def _reply(self, row):
        if not row:
            return None
        row = dict(row)
        for name in ('photos', 'commissions'):
            row[name] = json.loads(row[name] or '[]')
        row['song'] = json.loads(row['song']) if row['song'] else None
        row['stationery'] = json.loads(row['stationery']) if row.get('stationery') else None
        row['state'] = 'draft' if not row['sealed_at'] else (
            'travelling' if row['recipient'] == 'future' and row['deliver_on'] and row['deliver_on'] > iso(self.today())
            else 'sealed')
        return row

    def reply(self, rid):
        return self._reply(self._row('SELECT * FROM replies WHERE id = ?', (rid,)))

    def replies(self, start=None, end=None):
        sql, args = 'SELECT * FROM replies WHERE deleted_at IS NULL', []
        if start:
            sql += ' AND date >= ?'
            args.append(iso(parse_day(start)))
        if end:
            sql += ' AND date <= ?'
            args.append(iso(parse_day(end)))
        return [self._reply(r) for r in self._rows(sql + ' ORDER BY date DESC, created DESC', args)]

    def replies_with_song(self, track_id):
        """How many replies have this library song clipped in."""
        pattern = '%' + json.dumps({'id': track_id}, ensure_ascii=False)[1:-1] + '%'
        row = self._row('SELECT COUNT(*) AS n FROM replies WHERE deleted_at IS NULL AND song LIKE ?', (pattern,))
        return (row or {}).get('n') or 0

    def reply_for(self, day):
        """The newest reply written on a day, if any."""
        row = self._row('SELECT * FROM replies WHERE deleted_at IS NULL AND date = ? ORDER BY created DESC LIMIT 1',
                        (iso(parse_day(day)),))
        return self._reply(row)

    def _reply_fields(self, data):
        out = {}
        if 'body' in data:
            out['body'] = str(data.get('body') or '')[:200000]
        if 'mood' in data:
            if data['mood'] not in (None, '', *MOODS):
                raise ValueError('未知的心情邮票')
            out['mood'] = data['mood'] or None
        if 'weather' in data:
            if data['weather'] not in (None, '', *WEATHERS):
                raise ValueError('未知的天气邮票')
            out['weather'] = data['weather'] or None
        if 'song' in data:
            song = data['song']
            if song and not (isinstance(song, dict) and song.get('title')):
                raise ValueError('夹进信里的歌缺少歌名')
            keep = ('id', 'title', 'artist', 'album', 'has_cover', 'platform')
            out['song'] = json.dumps({k: song.get(k) for k in keep}, ensure_ascii=False) if song else None
        if 'stationery' in data:
            chosen = clean_stationery(data['stationery'])
            out['stationery'] = json.dumps(chosen, ensure_ascii=False) if chosen else None
        if 'photos' in data:
            photos = [str(p) for p in data['photos'] or [] if isinstance(p, str)][:12]
            out['photos'] = json.dumps(photos)
        if 'attach_commissions' in data:
            out['attach_commissions'] = 1 if data['attach_commissions'] else 0
        if 'starred' in data:
            out['starred'] = 1 if data['starred'] else 0
        return out

    def create_reply(self, data):
        day = iso(parse_day(data.get('date') or self.today()))
        fields = self._reply_fields(data)
        now = self.clock()
        fields.update(id=new_id(), date=day, created=now, updated=now)
        with self._tx() as db:
            db.execute(f'INSERT INTO replies ({", ".join(fields)}) VALUES ({", ".join("?" * len(fields))})',
                       tuple(fields.values()))
        return self.reply(fields['id'])

    def update_reply(self, rid, data):
        fields = self._reply_fields(data)
        with self._lock:
            self._check_revision('replies', rid, data.get('revision'), self.reply)
            current = self.reply(rid)
            if current['sealed_at'] and set(fields) - {'starred'}:
                raise ValueError('这封信已经封缄，先拆开才能修改')
            if fields:
                fields['updated'] = self.clock()
                sets = ', '.join(f'{k} = ?' for k in fields)
                with self._tx() as db:
                    db.execute(f'UPDATE replies SET {sets}, revision = revision + 1 WHERE id = ?',
                               (*fields.values(), rid))
        return self.reply(rid)

    def seal_reply(self, rid, recipient='violet', deliver_on=None, revision=None, stationery=None):
        if recipient not in ('violet', 'future'):
            raise ValueError('未知的收信人')
        with self._lock:
            self._check_revision('replies', rid, revision, self.reply)
            current = self.reply(rid)
            if not current['body'].strip():
                raise ValueError('信纸还是空的')
            deliver = None
            if recipient == 'future':
                deliver = parse_day(deliver_on, '投递日期') if deliver_on else None
                if not deliver or deliver <= self.today():
                    raise ValueError('寄给未来的信，投递日期要在今天之后')
                deliver = iso(deliver)
            done = []
            if current['attach_commissions']:
                done = [{'id': c['id'], 'title': c['title'], 'client': c['client']}
                        for c in self.completed_on(current['date'])]
            now = self.clock()
            # The stationery (and the sign-off) are fixed on the letter the moment it is sealed.
            kept = clean_stationery(stationery, current.get('stationery') or {}) if isinstance(stationery, dict) \
                else current.get('stationery')
            with self._tx() as db:
                db.execute("""UPDATE replies SET recipient = ?, deliver_on = ?, sealed_at = ?, commissions = ?,
                              stationery = ?, updated = ?, revision = revision + 1 WHERE id = ?""",
                           (recipient, deliver, now, json.dumps(done, ensure_ascii=False),
                            json.dumps(kept, ensure_ascii=False) if kept else None, now, rid))
        return self.reply(rid)

    def unseal_reply(self, rid):
        with self._tx() as db:
            db.execute("""UPDATE replies SET sealed_at = NULL, recipient = 'violet', deliver_on = NULL,
                          revision = revision + 1, updated = ? WHERE id = ? AND deleted_at IS NULL""",
                       (self.clock(), rid))
        return self.reply(rid)

    def open_reply(self, rid):
        with self._tx() as db:
            db.execute('UPDATE replies SET opened_at = COALESCE(opened_at, ?) WHERE id = ?', (self.clock(), rid))
        return self.reply(rid)

    def arrivals(self, day=None):
        """Letters to the future whose day has come and which have not been opened yet."""
        day = iso(day or self.today())
        rows = self._rows("""SELECT * FROM replies WHERE deleted_at IS NULL AND recipient = 'future'
                             AND sealed_at IS NOT NULL AND deliver_on <= ? AND opened_at IS NULL
                             ORDER BY deliver_on""", (day,))
        return [self._reply(r) for r in rows]

    # ------------------------------------------------------------ listening and days

    def record_listen(self, track):
        day = iso(self.today())
        with self._tx() as db:
            db.execute("""INSERT INTO listens (day, track_id, title, artist, album, has_cover, count, last)
                          VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                          ON CONFLICT (day, track_id) DO UPDATE SET count = count + 1, last = excluded.last""",
                       (day, track['id'], track.get('title') or '', track.get('artist') or '', track.get('album') or '',
                        1 if track.get('has_cover') else 0, self.clock()))

    def listens(self, day):
        return self._rows('SELECT * FROM listens WHERE day = ? ORDER BY last DESC', (iso(parse_day(day)),))

    def completed_on(self, day):
        day = parse_day(day)
        start = datetime.combine(day, datetime.min.time()).timestamp()
        end = start + 86400
        rows = self._rows("""SELECT * FROM commissions WHERE deleted_at IS NULL AND status = 'done'
                             AND completed_at >= ? AND completed_at < ? ORDER BY completed_at""", (start, end))
        return [self._commission(r) for r in rows]

    def day(self, value):
        """Everything that happened on one date, for the stamp book's detail panel."""
        day = parse_day(value)
        key = iso(day)
        return {
            'almanac': almanac.describe(day, with_season=True),
            'due': [self._commission(r) for r in self._rows(
                "SELECT * FROM commissions WHERE deleted_at IS NULL AND due_date = ? ORDER BY status, due_time", (key,))],
            'completed': self.completed_on(day),
            'appointments': self.occurrences(day, day),
            'replies': self.replies(day, day),
            'listens': self.listens(day),
            'focus_seconds': (self._row('SELECT SUM(seconds) AS s FROM focus WHERE day = ?', (key,)) or {}).get('s') or 0,
        }

    def month(self, year, month):
        """Per-day marks for a month view (plus the days before/after shown in the grid)."""
        first = date(year, month, 1)
        start = first - timedelta(days=first.weekday())
        end = start + timedelta(days=41)
        a, b = iso(start), iso(end)
        days = {iso(start + timedelta(days=i)): {'due': 0, 'open': 0, 'done': 0, 'appointments': [],
                                                  'reply': None, 'listens': 0, 'focus': 0}
                for i in range(42)}
        for r in self._rows("""SELECT due_date, status FROM commissions WHERE deleted_at IS NULL
                               AND due_date BETWEEN ? AND ?""", (a, b)):
            days[r['due_date']]['due'] += 1
            days[r['due_date']]['open'] += r['status'] == 'open'
        for r in self._rows("""SELECT completed_at FROM commissions WHERE deleted_at IS NULL AND status = 'done'
                               AND completed_at IS NOT NULL"""):
            key = iso(datetime.fromtimestamp(r['completed_at']).date())
            if key in days:
                days[key]['done'] += 1
        for r in self.occurrences(start, end):
            days[r['on']]['appointments'].append({'id': r['id'], 'title': r['title'], 'kind': r['kind'],
                                                  'start': r['start'], 'years': r.get('years')})
        for r in self._rows("""SELECT date, mood, weather, sealed_at, recipient FROM replies WHERE deleted_at IS NULL
                               AND date BETWEEN ? AND ? ORDER BY created""", (a, b)):
            days[r['date']]['reply'] = {'mood': r['mood'], 'weather': r['weather'], 'sealed': bool(r['sealed_at']),
                                        'recipient': r['recipient']}
        for r in self._rows('SELECT day, SUM(count) AS n FROM listens WHERE day BETWEEN ? AND ? GROUP BY day', (a, b)):
            days[r['day']]['listens'] = r['n']
        for r in self._rows('SELECT day, SUM(seconds) AS s FROM focus WHERE day BETWEEN ? AND ? GROUP BY day', (a, b)):
            days[r['day']]['focus'] = r['s']
        out = []
        for key, marks in days.items():
            info = almanac.describe(key)
            out.append(dict(marks, date=key, label=info['label'], term=info['term'], festivals=info['festivals'],
                            lunar=info['lunar'] and info['lunar']['month_name'] + info['lunar']['day_name']))
        return out

    # ------------------------------------------------------------ the desk and the daily letter

    def today_view(self):
        today = self.today()
        key = iso(today)
        open_items = [self._commission(r) for r in self._rows(
            """SELECT * FROM commissions WHERE deleted_at IS NULL AND status = 'open' AND due_date <= ?
               ORDER BY due_date, due_time IS NULL, due_time, number""", (key,))]
        # The desk looks a week ahead: tomorrow and the rest of the week, then just how many more are waiting.
        week_end = iso(today + timedelta(days=7))
        upcoming = [self._commission(r) for r in self._rows(
            """SELECT * FROM commissions WHERE deleted_at IS NULL AND status = 'open' AND due_date > ? AND due_date <= ?
               ORDER BY due_date, due_time IS NULL, due_time, number""", (key, week_end))]
        later = (self._row("""SELECT COUNT(*) AS n FROM commissions WHERE deleted_at IS NULL AND status = 'open'
                              AND due_date > ?""", (week_end,)) or {}).get('n') or 0
        ahead = self.occurrences(today, today + timedelta(days=30))
        last_week_start = today - timedelta(days=today.weekday() + 7)
        weekly = None
        if today.weekday() == 6:
            weekly = self.weekly(iso_week(today))
        elif today.weekday() <= 1:
            candidate = self.weekly(iso_week(last_week_start))
            if not candidate['sealed_at']:
                weekly = candidate
        return {
            'date': key,
            'almanac': almanac.describe(today, with_season=True),
            'commissions': open_items,
            'done_today': self.completed_on(today),
            'upcoming': upcoming,
            'later': later,
            'appointments': [a for a in ahead if a['on'] == key],
            'ahead': [a for a in ahead if a['on'] != key][:6],
            'reply': self.reply_for(today),
            'arrivals': self.arrivals(today),
            'weekly': weekly,
            'focus_seconds': (self._row('SELECT SUM(seconds) AS s FROM focus WHERE day = ?', (key,)) or {}).get('s') or 0,
        }

    def letter_notes(self, day):
        """Postscripts for Violet's letter of `day`: things she would mention."""
        day = parse_day(day)
        key = iso(day)
        notes = []
        info = almanac.describe(day)
        if info['term'] or info['festivals']:
            notes.append(f'今天是{"、".join(([info["term"]] if info["term"] else []) + info["festivals"])}。')
        season = almanac.season(day)
        if season and (day - parse_day(season['since'])).days in (0, 5, 10):
            # A new pentad begins: say what the old almanac says is happening outside.
            notes.append(f'{season["term"]}{"一二三"[season["index"]]}候，「{season["hou"]}」——{season["gloss"]}。')
        overdue = [c['title'] for c in self._rows(
            """SELECT title FROM commissions WHERE deleted_at IS NULL AND status = 'open' AND due_date < ?
               ORDER BY due_date LIMIT 3""", (key,))]
        if overdue:
            notes.append('还有{}件委托没有办完：{}。不急，今天接着来。'.format(
                len(overdue) if len(overdue) < 3 else '几', '、'.join(f'「{t}」' for t in overdue)))
        due = self._row("""SELECT COUNT(*) AS n FROM commissions WHERE deleted_at IS NULL AND status = 'open'
                           AND due_date = ?""", (key,))['n']
        if due:
            notes.append(f'今天有 {due} 份委托等着你。')
        for item in self.occurrences(day, day + timedelta(days=3)):
            if item['kind'] == 'anniversary':
                gap = (parse_day(item['on']) - day).days
                years = f'（第 {item["years"]} 年）' if item.get('years') else ''
                notes.append(f'今天是「{item["title"]}」{years}。' if gap == 0 else f'再过 {gap} 天就是「{item["title"]}」了。')
            elif item['on'] == key:
                when = f'{item["start"]} ' if item['start'] else ''
                notes.append(f'今天{when}有一个约定：「{item["title"]}」。')
        try:
            for row in self._rows('SELECT title, day FROM pressed WHERE substr(day, 6) = ? AND day < ? '
                                  'ORDER BY day LIMIT 1', (key[5:], key)):
                years = day.year - int(row['day'][:4])
                when = '一年' if years == 1 else f'{years} 年'
                notes.append(f'{when}前的今天，你把《{row["title"]}》压进了书里。')
        except sqlite3.OperationalError:
            pass
        if self.arrivals(day):
            notes.append('另外，邮差说今天还有一封来自过去的你的信。')
        if day.weekday() == 6:
            notes.append('今天是周日，这一周的封存袋放在书桌上了。')
        return notes

    # ------------------------------------------------------------ weekly seal

    def week_summary(self, week):
        start, end = week_bounds(week)
        a, b = iso(start), iso(end)
        t0 = datetime.combine(start, datetime.min.time()).timestamp()
        t1 = t0 + 7 * 86400
        done = [self._commission(r) for r in self._rows(
            """SELECT * FROM commissions WHERE deleted_at IS NULL AND status = 'done' AND completed_at >= ?
               AND completed_at < ? ORDER BY completed_at""", (t0, t1))]
        replies = self.replies(start, end)
        songs = self._rows("""SELECT track_id, title, artist, has_cover, SUM(count) AS count FROM listens
                              WHERE day BETWEEN ? AND ? GROUP BY track_id ORDER BY count DESC, MAX(last) DESC
                              LIMIT 3""", (a, b))
        listens = (self._row('SELECT SUM(count) AS n FROM listens WHERE day BETWEEN ? AND ?', (a, b)) or {}).get('n') or 0
        focus = (self._row('SELECT SUM(seconds) AS s FROM focus WHERE day BETWEEN ? AND ?', (a, b)) or {}).get('s') or 0
        moods = [{'date': r['date'], 'mood': r['mood'], 'weather': r['weather']} for r in reversed(replies)
                 if r['mood'] or r['weather']]
        try:  # the shelf's table lives in the same database once the shelf has been opened
            pressed = self._rows('SELECT title, artist, track_id, has_cover FROM pressed WHERE day BETWEEN ? AND ? '
                                 'ORDER BY pressed_at', (a, b))
        except sqlite3.OperationalError:
            pressed = []
        return {'start': a, 'end': b, 'done': [{'title': c['title'], 'client': c['client']} for c in done],
                'replies': len([r for r in replies if r['sealed_at']]), 'moods': moods, 'songs': songs,
                'listens': listens, 'focus_seconds': focus, 'pressed': pressed}

    def weekly(self, week):
        row = self._row('SELECT * FROM weekly WHERE week = ?', (week,))
        if row and row['sealed_at']:
            return dict(row, summary=json.loads(row['summary'] or '{}'))
        summary = self.week_summary(week)
        return {'week': week, 'start': summary['start'], 'end': summary['end'], 'summary': summary,
                'note': (row or {}).get('note', ''), 'sealed_at': None, 'revision': (row or {}).get('revision', 0)}

    def seal_week(self, week, note=''):
        start, end = week_bounds(week)
        if start > self.today():
            raise ValueError('这一周还没开始')
        summary = self.week_summary(week)
        now = self.clock()
        with self._tx() as db:
            db.execute("""INSERT INTO weekly (week, start, end, summary, note, sealed_at) VALUES (?, ?, ?, ?, ?, ?)
                          ON CONFLICT (week) DO UPDATE SET summary = excluded.summary, note = excluded.note,
                          sealed_at = excluded.sealed_at, revision = revision + 1""",
                       (week, iso(start), iso(end), json.dumps(summary, ensure_ascii=False), str(note or '')[:2000], now))
        return self.weekly(week)

    def sealed_weeks(self):
        return [dict(r, summary=json.loads(r['summary'] or '{}'))
                for r in self._rows('SELECT * FROM weekly WHERE sealed_at IS NOT NULL ORDER BY week DESC')]

    # ------------------------------------------------------------ reminders

    def due_reminders(self, now=None):
        """Reminders whose moment has come and that were not delivered yet. Marks them delivered."""
        now = now or self.clock()
        fired = []
        with self._lock:
            for row in self._rows("""SELECT * FROM commissions WHERE deleted_at IS NULL AND status = 'open'
                                     AND due_date IS NOT NULL AND remind IS NOT NULL"""):
                stamp = f'{row["due_date"]} {row["due_time"] or "09:00"} {row["remind"]}'
                if row['reminded_for'] == stamp:
                    continue
                at = datetime.fromisoformat(f'{row["due_date"]}T{row["due_time"] or "09:00"}').timestamp() - row['remind'] * 60
                if at <= now:
                    self._mark('commissions', row['id'], stamp)
                    if now - at <= REMIND_GRACE:
                        fired.append({'kind': 'commission', 'id': row['id'], 'title': row['title'],
                                      'when': row['due_time'] or '', 'date': row['due_date'], 'late': now - at > 120,
                                      'client': row['client']})
            today = date.fromtimestamp(now)
            for row in self.occurrences(today - timedelta(days=1), today + timedelta(days=8)):
                if row['remind'] is None:
                    continue
                start = row['start'] or '09:00'
                stamp = f'{row["on"]} {start} {row["remind"]}'
                if row['reminded_for'] == stamp:
                    continue
                at = datetime.fromisoformat(f'{row["on"]}T{start}').timestamp() - row['remind'] * 60
                if at <= now:
                    self._mark('appointments', row['id'], stamp)
                    if now - at <= REMIND_GRACE:
                        fired.append({'kind': row['kind'], 'id': row['id'], 'title': row['title'],
                                      'when': row['start'] or '', 'date': row['on'], 'late': now - at > 120,
                                      'place': row['place']})
        return fired

    def _mark(self, table, record_id, stamp):
        with self._tx() as db:
            db.execute(f'UPDATE {table} SET reminded_for = ? WHERE id = ?', (stamp, record_id))


class _Transaction:
    """BEGIN IMMEDIATE … COMMIT under the desk lock; rolls back on any error."""

    def __init__(self, desk):
        self.desk = desk

    def __enter__(self):
        self.desk._lock.acquire()
        try:
            self.desk.db.execute('BEGIN IMMEDIATE')
        except Exception:
            self.desk._lock.release()
            raise
        return self.desk.db

    def __exit__(self, kind, error, trace):
        try:
            self.desk.db.execute('COMMIT' if kind is None else 'ROLLBACK')
        finally:
            self.desk._lock.release()
        return False
