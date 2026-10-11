"""鸿雁：从学校网站取回通知（驿路），再按收件人名片拣出和你有关的（拣信）。

- 驿路是声明式的 JSON 规则：去哪个网址、列表里每一条在哪、标题 / 链接 / 日期怎么取、正文在哪。
  遇到怪网站可以附一小段脚本；脚本只在 QuickJS 沙盒里跑——没有网络、没有文件、限时限内存，
  只能把 Violet 取回的网页文字变成通知列表。
- 拣信全在本机：名片里每项「关心的事」是一组关键词，标题命中算得重、正文命中算得轻，
  再看学院、年级、本科 / 研究生和「不想看的事」。每封信都写明理由，用户纠错时 Violet 只提建议，不偷偷学。
- 和书桌共用 desk.db（每日备份自然带上）；门户登录得到的会话用 Windows DPAPI 加密，单独存在数据文件夹。
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from violet_desk import iso

if getattr(sys, 'frozen', False):
    PACK_DIR = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)) / 'data' / 'routes'
else:
    PACK_DIR = Path(__file__).resolve().parent / 'data' / 'routes'

SCHEMA = """
CREATE TABLE IF NOT EXISTS geese_routes (
    id TEXT PRIMARY KEY, pack TEXT NOT NULL, data TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
    trusted INTEGER NOT NULL DEFAULT 0, added REAL, last_fetch REAL, last_ok REAL, next_fetch REAL,
    error TEXT, fails INTEGER NOT NULL DEFAULT 0, etag TEXT, modified TEXT, seen INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS geese_letters (
    id TEXT PRIMARY KEY, route_id TEXT NOT NULL, route_name TEXT NOT NULL DEFAULT '', title TEXT NOT NULL,
    link TEXT NOT NULL, published TEXT, summary TEXT NOT NULL DEFAULT '', content TEXT, body TEXT NOT NULL DEFAULT '',
    attachments TEXT NOT NULL DEFAULT '[]', detail TEXT NOT NULL DEFAULT 'none', fetched_at REAL NOT NULL,
    score REAL NOT NULL DEFAULT 0, passed INTEGER NOT NULL DEFAULT 0, cubby TEXT, reasons TEXT NOT NULL DEFAULT '[]',
    deadline TEXT, deadline_text TEXT, read_at REAL, pinned INTEGER NOT NULL DEFAULT 0, archived_at REAL,
    commission_id TEXT, appointment_id TEXT, notified INTEGER NOT NULL DEFAULT 0, quiet INTEGER NOT NULL DEFAULT 0,
    feedback TEXT);
CREATE INDEX IF NOT EXISTS geese_letters_fetched ON geese_letters (fetched_at);
CREATE INDEX IF NOT EXISTS geese_letters_route ON geese_letters (route_id);
"""

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/126.0 Safari/537.36 Violet-Geese/1')
HOST_GAP = 1.5            # seconds between two requests to the same school site
MAX_BODY = 4 * 1024 * 1024
MIN_INTERVAL, DEFAULT_INTERVAL, MAX_INTERVAL = 30, 120, 7 * 1440   # minutes
DETAIL_CAP, BACKFILL_DETAIL_CAP = 12, 30
BACKFILL_DAYS, BACKFILL_PAGES = 35, 3
UNOPENED_DAYS, STALE_DAYS, ARCHIVE_KEEP_DAYS = 30, 14, 365
PASS, VERY = 4, 12
FRESH_DAYS = 3  # a notice published longer ago than this is never announced as new
URGENT_DAYS = 3
QUIET_HOURS = (23, 7)
SCRIPT_SECONDS, SCRIPT_MEMORY = 2.0, 64 * 1024 * 1024
MAX_ITEMS = 200

PRESET_CARES = [
    {'id': 'contest', 'name': '竞赛', 'keywords': ['竞赛', '大赛', '挑战杯', '数学建模', 'ACM', '程序设计', '创新创业',
                                                   '互联网+', '大创', '选拔赛', '赛事']},
    {'id': 'exam', 'name': '考试', 'keywords': ['考试', '补考', '重修', '缓考', '四六级', 'CET', '期末', '期中', '考场', '免修']},
    {'id': 'aid', 'name': '奖助', 'keywords': ['奖学金', '助学金', '资助', '评优', '评奖', '勤工助学', '困难认定', '励志']},
    {'id': 'course', 'name': '选课', 'keywords': ['选课', '培养方案', '学分', '退课', '辅修', '转专业', '教学安排', '学籍', '课表']},
    {'id': 'lecture', 'name': '讲座', 'keywords': ['讲座', '报告会', '学术报告', '论坛', '沙龙', '讲堂', '分享会']},
    {'id': 'career', 'name': '实习就业', 'keywords': ['实习', '招聘', '就业', '宣讲会', '双选会', '校招', '职业发展']},
    {'id': 'abroad', 'name': '出国交流', 'keywords': ['交换生', '交流项目', '出国', '境外', '访学', '暑期学校', '留学', '海外']},
    {'id': 'postgrad', 'name': '推免考研', 'keywords': ['推免', '保研', '免试', '夏令营', '考研', '研究生招生']},
    {'id': 'activity', 'name': '活动', 'keywords': ['志愿', '社会实践', '社团', '文化活动', '文艺', '运动会', '支教', '模拟联合国']},
]
DEFAULT_CARES = ('contest', 'exam', 'aid', 'course')
DEFAULT_AVOID = ['采购', '竞选结果', '竞选公告', '招标', '中标', '询价', '成交', '比选', '维修']
LEVELS = ('undergrad', 'graduate')
MODES = ('arrive', 'morning')
GRADE_NAMES = ('大一', '大二', '大三', '大四', '大五')

TITLE_WEIGHT, BODY_WEIGHT = 4, 1
ATTACHMENT_EXTS = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar', '.7z', '.txt', '.wps')
SAFE_TAGS = {'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'td', 'th',
             'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'blockquote', 'sup', 'sub'}
BLOCK_TAGS = {'div', 'section', 'article', 'center', 'font', 'span', 'label', 'small', 'big'}
STOP_WORDS = re.compile(r'关于做好|关于开展|关于举办|关于组织|关于启动|关于发布|关于公布|关于|的通知|的公告|的公示|通知|公告|公示|'
                        r'举办|开展|组织|启动|做好|进行|工作|年度|学年|第[一二三四五六七八九十\d]+[届期批次]|20\d\d(?:-20\d\d)?[年届级]?|'
                        r'西北工业大学|西工大|我校|学校|本科生?|研究生|大学生|报名|申报|评选|结果|名单|拟|有关|事项|安排|'
                        r'[及和与暨的、，,。：:;；“”"\'（）()《》【】\[\]\s—\-]+')


class LoginNeeded(Exception):
    """The route needs a portal session that is missing or has expired."""


class RouteError(ValueError):
    pass


# ---------------------------------------------------------------- small helpers

def _text(value, limit):
    return re.sub(r'\s+', ' ', str(value or '')).strip()[:limit]


def letter_id(route_id, link):
    return hashlib.sha1(f'{route_id}|{link}'.encode('utf-8')).hexdigest()[:20]


def short_title(title, limit=26):
    """「关于…的通知」 reads better without its envelope."""
    core = re.sub(r'^关于(?:做好|开展|举办|组织|启动)?', '', title or '')
    core = re.sub(r'的(?:通知|公告|公示)$', '', core).strip() or title or ''
    return core if len(core) <= limit else core[:limit - 1] + '…'


DATE_FULL = re.compile(r'(20\d{2})\s*[年\-/.]\s*(\d{1,2})\s*[月\-/.]\s*(\d{1,2})\s*[日号]?')
DATE_MD_Y = re.compile(r'(\d{1,2})[.\-/](\d{1,2})\s+(20\d{2})')
DATE_MD = re.compile(r'(?<![\d年.\-/])(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]')


def _safe_date(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def parse_date(text, ref=None):
    """A publication date from a list cell: 2026-10-09, 2026/05/06, 2026年9月11日, 08.26 2026, 10月9日…"""
    text = str(text or '')
    match = DATE_FULL.search(text)
    if match:
        return _safe_date(*match.groups())
    match = DATE_MD_Y.search(text)
    if match:
        return _safe_date(match.group(3), match.group(1), match.group(2))
    match = DATE_MD.search(text) or re.search(r'(?<!\d)(\d{1,2})-(\d{1,2})(?!\d)', text)
    if match:
        ref = ref or date.today()
        found = _safe_date(ref.year, *match.groups())
        if found and found > ref + timedelta(days=31):
            found = _safe_date(ref.year - 1, *match.groups())
        return found
    return None


DEADLINE_CUE = re.compile(r'截止|截至|之前|以前|\d\s*[日号]\s*(?:[（(][^）)]{0,4}[）)])?\s*(?:[上中下早晚]午?)?\s*'
                          r'(?:\d{1,2}[:：]\d{2})?\s*(?:前|止)|(?:报名|提交|申报|申请)(?:时间|日期|期限)')


def find_deadline(text, published=None):
    """The first date a reader must act by: a date in a clause that says 截止 / 之前 / 报名时间….
    Returns (date, the clause) or (None, '')."""
    published = published or date.today()
    best = None
    for clause in re.split(r'[。；;\n！!？?]', text or ''):
        if not DEADLINE_CUE.search(clause):
            continue
        dates = []
        for match in DATE_FULL.finditer(clause):
            found = _safe_date(*match.groups())
            if found:
                dates.append(found)
        stripped = DATE_FULL.sub(' ', clause)
        for match in DATE_MD.finditer(stripped):
            found = _safe_date(published.year, *match.groups())
            if found and found < published - timedelta(days=30):
                found = _safe_date(published.year + 1, *match.groups())
            if found:
                dates.append(found)
        dates = [d for d in dates if d >= published - timedelta(days=1)]
        if not dates:
            continue
        when = max(dates)  # 「10月1日至10月11日」: the end of the window
        if best is None or when < best[0]:
            best = (when, _text(clause, 80))
    return best or (None, '')


def grade_tokens(card, today=None):
    """Words that mean the reader's own year, and words that mean somebody else's."""
    entry = card.get('entry_year')
    if not entry:
        return [], []
    today = today or date.today()
    span = 4 if card.get('level') != 'graduate' else 3
    year = today.year - entry + (1 if today.month >= 9 else 0)
    mine = [f'{entry}级', f'{entry + span}届']
    if card.get('level') != 'graduate' and 1 <= year <= len(GRADE_NAMES):
        mine.append(GRADE_NAMES[year - 1])
    others = []
    for other in range(entry - 5, entry + 3):
        if other != entry:
            others += [f'{other}级', f'{other + span}届']
    return mine, others


def _distinct(hits):
    """Drop a hit that is part of a longer hit (建模 inside 数学建模)."""
    return [h for h in hits if not any(h != o and h in o for o in hits)]


# ---------------------------------------------------------------- the card

def default_card():
    return {'school': 'nwpu', 'college': '', 'level': 'undergrad', 'entry_year': None,
            'cares': [dict(c, keywords=list(c['keywords'])) for c in PRESET_CARES if c['id'] in DEFAULT_CARES],
            'avoid': list(DEFAULT_AVOID), 'mode': 'arrive', 'urgent': True}


def clean_card(data):
    if not isinstance(data, dict):
        raise ValueError('名片格式不对')
    card = default_card()
    card['school'] = _text(data.get('school') or 'nwpu', 40)
    card['college'] = _text(data.get('college'), 40)
    card['level'] = data.get('level') if data.get('level') in LEVELS else 'undergrad'
    entry = data.get('entry_year')
    if entry not in (None, ''):
        entry = int(entry)
        if not 2000 <= entry <= date.today().year + 1:
            raise ValueError('入学年份不对')
    card['entry_year'] = entry or None
    cares, seen = [], set()
    for care in data.get('cares') or []:
        if not isinstance(care, dict):
            continue
        name = _text(care.get('name'), 12)
        words = []
        for word in care.get('keywords') or []:
            word = _text(word, 20)
            if word and word not in words:
                words.append(word)
        if not name or not words:
            continue
        cid = re.sub(r'[^a-z0-9-]', '', str(care.get('id') or '').lower())[:24] or 'c' + hashlib.sha1(name.encode()).hexdigest()[:6]
        if cid in seen or cid == 'misc':
            continue
        seen.add(cid)
        cares.append({'id': cid, 'name': name, 'keywords': words[:40]})
    if len(cares) > 9:
        raise ValueError('「关心的事」最多九项')
    card['cares'] = cares
    avoid = []
    for word in data['avoid'] if isinstance(data.get('avoid'), list) else DEFAULT_AVOID:
        word = _text(word, 20)
        if word and word not in avoid:
            avoid.append(word)
    card['avoid'] = avoid[:60]
    card['mode'] = data.get('mode') if data.get('mode') in MODES else 'arrive'
    card['urgent'] = bool(data.get('urgent', True))
    return card


class Sorter:
    """拣信: score one letter against the card, with the reasons spelled out."""

    def __init__(self, card, colleges=(), today=None):
        self.card = card
        self.today = today or date.today()
        self.colleges = colleges or []
        mine = next((c for c in self.colleges if c['name'] == card.get('college')), None)
        self.mine = (mine or {}).get('aliases') or ([card['college']] if card.get('college') else [])
        self.others = [a for c in self.colleges if c['name'] != card.get('college') for a in c.get('aliases') or [c['name']]]
        self.grade_mine, self.grade_others = grade_tokens(card, self.today)

    def score(self, title, body='', route=None, feedback=None):
        title, body = title or '', (body or '')[:8000]
        score, reasons, best = 0.0, [], (0, None, [])
        for care in self.card.get('cares') or []:
            in_title = _distinct([k for k in care['keywords'] if k.casefold() in title.casefold()])
            in_body = _distinct([k for k in care['keywords'] if k not in in_title and k.casefold() in body.casefold()])
            value = TITLE_WEIGHT * min(len(in_title), 2) + BODY_WEIGHT * min(len(in_body), 3)
            if value > best[0]:
                best = (value, care, in_title + in_body)
        if best[1]:
            score += best[0]
            reasons += best[2][:3]
        own_route = bool(route and route.get('college') and route['college'] == self.card.get('college'))
        if any(a in title for a in self.mine):
            score += 3
            reasons.append(self.card['college'])
        elif any(a in title for a in self.others):
            score -= 3
        elif own_route:
            score += 2
            reasons.append(f'{route["college"]}的通知')
        elif any(a in body for a in self.mine):
            score += 1
            reasons.append(self.card['college'])
        if any(t in title for t in self.grade_mine):
            score += 3
            reasons.append(next(t for t in self.grade_mine if t in title))
        elif any(t in title for t in self.grade_others):
            score -= 2
        elif any(t in body for t in self.grade_mine):
            score += 1
            reasons.append(next(t for t in self.grade_mine if t in body))
        grad_words = ('研究生', '博士', '硕士')
        if self.card.get('level') == 'graduate':
            if '本科' in title and not any(w in title for w in grad_words):
                score -= 3
        elif any(w in title for w in grad_words) and '本科' not in title:
            score -= 4
        avoided = [w for w in self.card.get('avoid') or [] if w in title]
        if avoided:
            score -= 8
            reasons = [f'不想看：{avoided[0]}']
        if feedback == 'useful':
            score += 10
            reasons.insert(0, '你说过这封有用')
        elif feedback == 'not':
            score -= 10
            reasons = ['你说过以后别送这类']
        passed = score >= PASS
        cubby = None
        if passed:
            cubby = best[1]['id'] if best[1] and best[0] >= BODY_WEIGHT * 2 else 'misc'
        seen, unique = set(), []
        for reason in reasons:
            if reason not in seen:
                seen.add(reason)
                unique.append(reason)
        return {'score': score, 'passed': passed, 'cubby': cubby, 'reasons': unique[:4]}


# ---------------------------------------------------------------- routes and packs

def _selector(value, field):
    value = str(value or '').strip()
    if len(value) > 240:
        raise RouteError(f'选择器 {field} 太长了')
    return value


def clean_route(route, pack_id):
    if not isinstance(route, dict):
        raise RouteError('驿路格式不对')
    rid = str(route.get('id') or '').strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,47}', rid):
        raise RouteError(f'驿路 id「{rid}」只能用小写字母、数字和连字符')
    name = _text(route.get('name'), 30)
    if not name:
        raise RouteError(f'驿路「{rid}」需要一个名字')
    url = str(route.get('url') or '').strip()
    if urllib.parse.urlparse(url).scheme not in ('http', 'https'):
        raise RouteError(f'驿路「{name}」的网址必须以 http:// 或 https:// 开头')
    kind = route.get('type') or 'html'
    if kind not in ('html', 'rss', 'json'):
        raise RouteError(f'驿路「{name}」的类型只能是 html、rss 或 json')
    script = str(route.get('script') or '')
    if len(script) > 20000:
        raise RouteError(f'驿路「{name}」的脚本太长了（上限 20000 字）')
    lst = route.get('list') or {}
    if not isinstance(lst, dict):
        raise RouteError(f'驿路「{name}」的 list 必须是对象')
    if kind == 'html' and not lst.get('item') and 'function list' not in script:
        raise RouteError(f'驿路「{name}」需要 list.item 选择器，或在脚本里写 list(page)')
    detail = route.get('detail') or {}
    if not isinstance(detail, dict):
        raise RouteError(f'驿路「{name}」的 detail 必须是对象')
    interval = int(route.get('interval') or DEFAULT_INTERVAL)
    login = route.get('login')
    if login is not None and not isinstance(login, str):
        raise RouteError(f'驿路「{name}」的 login 应该写门户的 id')
    return {
        'id': rid, 'pack': pack_id, 'name': name, 'column': _text(route.get('column'), 20), 'type': kind, 'url': url,
        'home': str(route.get('home') or '').strip(), 'college': _text(route.get('college'), 40),
        'level': route.get('level') if route.get('level') in LEVELS else '',
        'interval': max(MIN_INTERVAL, min(interval, MAX_INTERVAL)),
        'list': {k: _selector(v, k) for k, v in lst.items() if k in ('item', 'items', 'title', 'link', 'date', 'summary',
                                                                     'next', 'drop', 'link_template')},
        'detail': {k: _selector(v, k) for k, v in detail.items() if k in ('content', 'date', 'attachments', 'drop')},
        'script': script, 'login': login or '',
    }


def clean_pack(data):
    """Validate a route pack (built-in or imported). Raises RouteError with a readable message."""
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except ValueError as error:
            raise RouteError(f'这不是一份有效的 JSON：{error}') from None
    if not isinstance(data, dict) or not str(data.get('format', '')).startswith('violet-routes/'):
        raise RouteError('这不是 Violet 的驿路包（缺少 "format": "violet-routes/1"）')
    pid = str(data.get('id') or '').strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,39}', pid):
        raise RouteError('驿路包需要一个 id（小写字母、数字、连字符）')
    routes = data.get('routes')
    if not isinstance(routes, list) or not routes:
        raise RouteError('驿路包里没有驿路')
    if len(routes) > 60:
        raise RouteError('一个驿路包最多 60 条驿路')
    cleaned = [clean_route(r, pid) for r in routes]
    ids = [r['id'] for r in cleaned]
    if len(set(ids)) != len(ids):
        raise RouteError('驿路包里有重复的驿路 id')
    colleges = []
    for college in data.get('colleges') or []:
        if isinstance(college, dict) and college.get('name'):
            aliases = [_text(a, 40) for a in college.get('aliases') or [] if _text(a, 40)]
            colleges.append({'name': _text(college['name'], 40), 'aliases': aliases or [_text(college['name'], 40)]})
    portals = {}
    for key, portal in (data.get('portals') or {}).items():
        if isinstance(portal, dict) and re.fullmatch(r'[a-z0-9-]{2,40}', str(key)):
            login, done = str(portal.get('login') or ''), str(portal.get('done') or '')
            if urllib.parse.urlparse(login).scheme == 'https' and done:
                re.compile(done)
                portals[key] = {'name': _text(portal.get('name') or key, 20), 'login': login, 'done': done,
                                'hosts': [str(h) for h in portal.get('hosts') or []][:8]}
    for route in cleaned:
        if route['login'] and route['login'] not in portals:
            raise RouteError(f'驿路「{route["name"]}」要登录的门户「{route["login"]}」在包里没有定义')
    return {'format': 'violet-routes/1', 'id': pid, 'name': _text(data.get('name') or pid, 30), 'short': _text(data.get('short'), 10),
            'author': _text(data.get('author'), 40), 'note': _text(data.get('note'), 200),
            'colleges': colleges, 'portals': portals, 'routes': cleaned}


def builtin_packs():
    packs = []
    for path in sorted(PACK_DIR.glob('*.json')):
        try:
            packs.append(clean_pack(path.read_text(encoding='utf-8')))
        except (OSError, RouteError, ValueError) as error:
            print(f'内置驿路包 {path.name} 读取失败：{error}', file=sys.stderr, flush=True)
    return packs


# ---------------------------------------------------------------- the script sandbox

SCRIPT_PRELUDE = r"""
var text = function (html) {
  return String(html == null ? '' : html)
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, '')
    .replace(/<br\s*\/?>/gi, '\n').replace(/<\/(p|div|li|tr)>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
    .replace(/&#(\d+);/g, function (m, n) { return String.fromCharCode(+n) }).replace(/&amp;/g, '&')
    .replace(/[ \t\r\f]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim();
};
var json = function (body) { try { return JSON.parse(body) } catch (e) { return null } };
var between = function (s, start, end) {
  s = String(s); var i = s.indexOf(start); if (i < 0) return ''; i += start.length;
  var j = s.indexOf(end, i); return j < 0 ? s.slice(i) : s.slice(i, j);
};
"""


def run_script(source, function, page):
    """Call `function(page)` from a route's script inside a fresh QuickJS context and return plain JSON data.
    The context has no network, file or host access; it is stopped after SCRIPT_SECONDS."""
    try:
        import quickjs
    except ImportError:
        raise RouteError('这条驿路带脚本，需要 quickjs（pip install quickjs）') from None
    context = quickjs.Context()
    context.set_memory_limit(SCRIPT_MEMORY)
    context.set_time_limit(SCRIPT_SECONDS)
    context.set_max_stack_size(1024 * 1024)
    try:
        context.eval(SCRIPT_PRELUDE)
        context.eval(source)
        if context.eval(f'typeof {function}') != 'function':
            return None
        context.set('__page', json.dumps(page, ensure_ascii=False))
        raw = context.eval(f'JSON.stringify({function}(JSON.parse(__page)))')
    except Exception as error:  # quickjs.JSException, timeouts, memory
        raise RouteError(f'驿路脚本出错：{_text(error, 160)}') from None
    try:
        return json.loads(raw) if isinstance(raw, str) else None
    except ValueError:
        return None


# ---------------------------------------------------------------- fetching

class Page:
    def __init__(self, url, status, body='', etag=None, modified=None):
        self.url, self.status, self.body, self.etag, self.modified = url, status, body, etag, modified

    @property
    def not_modified(self):
        return self.status == 304


def _decode(raw, content_type):
    charset = None
    match = re.search(r'charset=([\w-]+)', content_type or '', re.I)
    if match:
        charset = match.group(1)
    else:
        match = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', raw[:4096], re.I)
        if match:
            charset = match.group(1).decode('ascii', 'ignore')
    for name in (charset, 'utf-8', 'gb18030'):
        if not name:
            continue
        try:
            return raw.decode('gb18030' if name.lower() in ('gb2312', 'gbk') else name)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode('utf-8', 'replace')


class Courier:
    """HTTP for the routes: one request at a time per school site, a little gap between them,
    conditional requests so an unchanged page costs almost nothing, and portal cookies when a route needs them."""

    def __init__(self, sessions=None, gap=HOST_GAP, opener=None):
        self.sessions = sessions
        self.gap = gap
        self.opener = opener or urllib.request.build_opener()
        self._hosts = {}
        self._lock = threading.Lock()

    def _host(self, host):
        with self._lock:
            return self._hosts.setdefault(host, [threading.Lock(), 0.0])

    def get(self, url, etag=None, modified=None, portal=None):
        host = urllib.parse.urlparse(url).hostname or ''
        headers = {'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/json,*/*;q=0.8',
                   'Accept-Language': 'zh-CN,zh;q=0.9'}
        if etag:
            headers['If-None-Match'] = etag
        if modified:
            headers['If-Modified-Since'] = modified
        if portal:
            cookie = self.sessions.cookie_header(portal['id'], host) if self.sessions else ''
            if not cookie:
                raise LoginNeeded(portal['name'])
            headers['Cookie'] = cookie
        slot = self._host(host)
        with slot[0]:
            wait = slot[1] + self.gap - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                with self.opener.open(urllib.request.Request(url, headers=headers), timeout=20) as response:
                    raw = response.read(MAX_BODY + 1)
                    final, status = response.geturl(), response.status
                    ctype = response.headers.get('Content-Type', '')
                    new_etag, new_modified = response.headers.get('ETag'), response.headers.get('Last-Modified')
            except urllib.error.HTTPError as error:
                if error.code == 304:
                    return Page(url, 304)
                if error.code in (401, 403) and portal:
                    raise LoginNeeded(portal['name']) from None
                raise
            finally:
                slot[1] = time.monotonic()
        if len(raw) > MAX_BODY:
            raise ValueError('网页太大了')
        if portal and any(urllib.parse.urlparse(final).hostname == h for h in portal.get('login_hosts') or []):
            raise LoginNeeded(portal['name'])
        return Page(final, status, _decode(raw, ctype), new_etag, new_modified)


# ---------------------------------------------------------------- extraction

def _soup(html):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, 'html.parser')


def _pick(node, selector, base=None):
    """`css` → text, `css@attr` → attribute (links made absolute). An empty css means the node itself."""
    if not selector:
        return ''
    css, _, attr = selector.partition('@')
    target = node.select_one(css.strip()) if css.strip() else node
    if target is None:
        return ''
    if attr:
        value = (target.get(attr.strip()) or '')
        value = ' '.join(value) if isinstance(value, list) else str(value)
        if attr.strip() in ('href', 'src') and base:
            value = urllib.parse.urljoin(base, value.strip())
        return value.strip()
    return re.sub(r'\s+', ' ', target.get_text(' ', strip=True))


def _json_path(data, path):
    for part in [p for p in str(path or '').split('.') if p]:
        if isinstance(data, list) and part.isdigit():
            data = data[int(part)] if int(part) < len(data) else None
        elif isinstance(data, dict):
            data = data.get(part)
        else:
            return None
    return data


def _items_from_script(route, page):
    found = run_script(route['script'], 'list', {'url': page.url, 'body': page.body})
    if found is None:
        return None
    if not isinstance(found, list):
        raise RouteError('驿路脚本的 list() 应该返回一个数组')
    return found


def extract_items(route, page):
    """The notices listed on one page: [{'title', 'link', 'date', 'summary'}], plus the next page's url."""
    raw, next_url = None, ''
    if route.get('script'):
        raw = _items_from_script(route, page)
    if raw is None:
        rules = route['list']
        if route['type'] == 'rss':
            raw = _rss_items(page.body)
        elif route['type'] == 'json':
            try:
                data = json.loads(page.body)
            except ValueError:
                raise RouteError('这条驿路返回的不是 JSON') from None
            rows = _json_path(data, rules.get('items'))
            raw = []
            for row in rows if isinstance(rows, list) else []:
                link = str(_json_path(row, rules.get('link')) or '')
                if rules.get('link_template'):
                    link = re.sub(r'\{([\w.]+)\}', lambda m: str(_json_path(row, m.group(1)) or ''), rules['link_template'])
                raw.append({'title': _json_path(row, rules.get('title')), 'link': link,
                            'date': _json_path(row, rules.get('date')), 'summary': _json_path(row, rules.get('summary'))})
        else:
            soup = _soup(page.body)
            nodes = soup.select(rules['item'])
            nodes = [n for n in nodes if not any(o is not n and n in o.parents for o in nodes)]  # keep the innermost
            raw = []
            for node in nodes:
                item = {'date': _pick(node, rules.get('date'), page.url),
                        'summary': _pick(node, rules.get('summary'), page.url),
                        'link': _pick(node, rules.get('link') or 'a@href', page.url)}
                if rules.get('drop'):
                    for gone in node.select(rules['drop']):
                        gone.decompose()
                item['title'] = _pick(node, rules.get('title') or 'a', page.url)
                raw.append(item)
            if rules.get('next'):
                next_url = _pick(soup, rules['next'], page.url)
    items, seen = [], set()
    for item in raw[:MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        title = _text(item.get('title'), 300)
        link = urllib.parse.urljoin(page.url, str(item.get('link') or '').strip())
        if not title or urllib.parse.urlparse(link).scheme not in ('http', 'https') or link in seen:
            continue
        seen.add(link)
        published = parse_date(item.get('date'))
        items.append({'title': title, 'link': link, 'published': iso(published) if published else '',
                      'summary': _text(item.get('summary'), 600)})
    return items, next_url


def _rss_items(body):
    try:
        root = ET.fromstring(body.encode('utf-8') if isinstance(body, str) else body)
    except ET.ParseError:
        raise RouteError('这条驿路返回的不是有效的 RSS / Atom') from None
    out = []
    strip = lambda tag: tag.rsplit('}', 1)[-1]
    for node in root.iter():
        if strip(node.tag) not in ('item', 'entry'):
            continue
        fields = {strip(c.tag): c for c in node}
        link = fields.get('link')
        href = (link.get('href') or link.text or '') if link is not None else ''
        when = next((fields[k].text for k in ('pubDate', 'published', 'updated', 'date') if k in fields), '')
        summary = next((fields[k].text for k in ('description', 'summary', 'content') if k in fields), '')
        out.append({'title': (fields['title'].text if 'title' in fields else ''), 'link': href,
                    'date': _rss_date(when), 'summary': re.sub(r'<[^>]+>', ' ', summary or '')})
    return out


def _rss_date(value):
    value = (value or '').strip()
    for fmt in ('%a, %d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S %Z'):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return value[:10]


def sanitize(node, base):
    """Keep the shape of a notice (paragraphs, lists, tables, bold, links) and nothing that can run or track."""
    from bs4 import Comment, NavigableString, Tag

    def walk(el):
        out = []
        for child in el.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                text = str(child).replace('\xa0', ' ')
                out.append(_escape(text))
                continue
            if not isinstance(child, Tag):
                continue
            name = child.name.lower()
            if name in ('script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'noscript', 'svg'):
                continue
            if name == 'img':
                out.append('<span class="img-note">（这里有一张图，原网页里可以看到）</span>')
                continue
            inner = walk(child)
            if name in SAFE_TAGS:
                attrs = ''
                if name == 'a':
                    href = urllib.parse.urljoin(base, (child.get('href') or '').strip())
                    if urllib.parse.urlparse(href).scheme not in ('http', 'https'):
                        out.append(inner)
                        continue
                    attrs = f' href="{_escape(href, True)}"'
                elif name in ('td', 'th'):
                    for key in ('colspan', 'rowspan'):
                        if str(child.get(key) or '').isdigit():
                            attrs += f' {key}="{child.get(key)}"'
                tag = 'h4' if name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6') else name
                out.append(f'<{tag}{attrs}>' + ('' if tag == 'br' else inner + f'</{tag}>'))
            elif name in BLOCK_TAGS and name in ('div', 'section', 'article', 'center'):
                out.append(f'<p>{inner}</p>' if inner.strip() else '')
            else:
                out.append(inner)
        return ''.join(out)

    html = walk(node)
    html = re.sub(r'<p>\s*</p>', '', html)
    return html[:200000]


def _escape(text, quote=False):
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return text.replace('"', '&quot;') if quote else text


def extract_detail(route, page):
    """The notice itself: sanitized html, plain text (for sorting and deadlines), attachments, date."""
    if route.get('script'):
        found = run_script(route['script'], 'detail', {'url': page.url, 'body': page.body})
        if isinstance(found, dict):
            content = str(found.get('content') or '')
            soup = _soup(content if '<' in content else '<p>' + _escape(content).replace('\n', '</p><p>') + '</p>')
            attachments = [{'name': _text(a.get('name'), 120), 'url': urllib.parse.urljoin(page.url, str(a.get('url') or ''))}
                           for a in found.get('attachments') or [] if isinstance(a, dict) and a.get('url')]
            return {'content': sanitize(soup, page.url), 'body': _text(soup.get_text('\n'), 20000),
                    'attachments': attachments[:30], 'published': iso(parse_date(found.get('date'))) if parse_date(found.get('date')) else ''}
    soup = _soup(page.body)
    rules = route.get('detail') or {}
    node = soup.select_one(rules['content']) if rules.get('content') else None
    if node is None:
        node = soup.select_one('.v_news_content, #vsb_content, #js_content, .rich_media_content, article, .article, .content, #content') or soup.body or soup
    if rules.get('drop'):
        for gone in node.select(rules['drop']):
            gone.decompose()
    text = re.sub(r'[ \t\xa0]+', ' ', node.get_text('\n'))
    text = re.sub(r'\n\s*\n+', '\n', text).strip()
    attachments, seen = [], set()
    pool = soup.select(rules['attachments']) if rules.get('attachments') else soup.find_all('a', href=True)
    for a in pool:
        href = urllib.parse.urljoin(page.url, (a.get('href') or '').strip())
        path = urllib.parse.urlparse(href).path.lower()
        if href in seen or not (('download' in path and '.jsp' in path) or path.endswith(ATTACHMENT_EXTS)):
            continue
        seen.add(href)
        name = _text(a.get_text(' ', strip=True), 120) or os.path.basename(path)
        attachments.append({'name': name, 'url': href})
    published = parse_date(_pick(soup, rules['date'])) if rules.get('date') else None
    return {'content': sanitize(node, page.url), 'body': text[:20000], 'attachments': attachments[:30],
            'published': iso(published) if published else ''}


# ---------------------------------------------------------------- portal sessions

class Sessions:
    """Cookies from a portal login, encrypted with the current Windows user's DPAPI key.
    Elsewhere (or if DPAPI fails) they live only in memory until Violet quits."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data = {}
        try:
            self._data = json.loads(_unprotect(self.path.read_bytes()).decode('utf-8'))
        except (OSError, ValueError):
            self._data = {}

    def status(self, portal):
        item = self._data.get(portal)
        return {'signed_in': bool(item and item.get('cookies')), 'saved': (item or {}).get('saved')}

    def save(self, portal, cookies):
        clean = [{'name': str(c.get('name')), 'value': str(c.get('value')), 'domain': str(c.get('domain') or '').lstrip('.'),
                  'path': str(c.get('path') or '/')} for c in cookies or [] if c.get('name')]
        with self._lock:
            self._data[portal] = {'cookies': clean, 'saved': time.time()}
            self._write()

    def forget(self, portal):
        with self._lock:
            self._data.pop(portal, None)
            self._write()

    def cookie_header(self, portal, host):
        item = self._data.get(portal) or {}
        pairs = [f'{c["name"]}={c["value"]}' for c in item.get('cookies') or []
                 if not c['domain'] or host == c['domain'] or host.endswith('.' + c['domain'])]
        return '; '.join(pairs)

    def _write(self):
        try:
            blob = _protect(json.dumps(self._data).encode('utf-8'))
        except OSError:
            return  # no DPAPI: keep the session for this run only
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_bytes(blob)
        os.replace(tmp, self.path)


def _dpapi(data, protect):
    if os.name != 'nt':
        raise OSError('DPAPI 只在 Windows 上可用')
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    buffer = ctypes.create_string_buffer(data, len(data))
    source, out = Blob(len(data), buffer), Blob()
    crypt = ctypes.windll.crypt32
    call = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    ok = call(ctypes.byref(source), None if not protect else 'Violet', None, None, None, 0x1, ctypes.byref(out))
    if not ok:
        raise OSError('DPAPI 加解密失败')
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _protect(data):
    return _dpapi(data, True)


def _unprotect(data):
    return _dpapi(data, False)


# ---------------------------------------------------------------- the geese

class Geese:
    def __init__(self, desk, data_dir, courier=None, today=None, publish=None, notify=None):
        self.desk = desk
        self.today = today or date.today
        self.publish = publish or (lambda kind, data: None)
        self.notify = notify or (lambda title, text: None)
        self.sessions = Sessions(Path(data_dir) / 'geese-sessions.bin')
        self.courier = courier or Courier(self.sessions)
        self._run_lock = threading.Lock()
        self.running = False
        self.progress = None
        with desk._lock:
            desk.db.executescript(SCHEMA)
        self.packs = {}
        for pack in builtin_packs():
            self.install_pack(pack, trusted=True, builtin=True)
        for pack in self._stored_packs().values():
            self.packs.setdefault(pack['id'], pack)
        self.tidy()

    # ------------------------------------------------------------ storage helpers

    def _rows(self, sql, args=()):
        return self.desk._rows(sql, args)

    def _row(self, sql, args=()):
        return self.desk._row(sql, args)

    def _tx(self):
        return self.desk._tx()

    def _now(self):
        return self.desk.clock()

    def _meta(self, key, default=None):
        row = self._row('SELECT value FROM meta WHERE key = ?', (key,))
        try:
            return json.loads(row['value']) if row else default
        except ValueError:
            return default

    def _set_meta(self, key, value):
        with self._tx() as db:
            db.execute('INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value',
                       (key, json.dumps(value, ensure_ascii=False)))

    def _stored_packs(self):
        return self._meta('geese_packs', {}) or {}

    # ------------------------------------------------------------ the card

    def card(self):
        return self._meta('geese_card')

    def save_card(self, data):
        card = clean_card(data)
        card['created'] = (self.card() or {}).get('created') or self._now()
        self._set_meta('geese_card', card)
        self.rescore()
        return card

    def sorter(self, card=None):
        card = card or self.card() or default_card()
        pack = self.packs.get(card.get('school')) or {}
        return Sorter(card, pack.get('colleges') or [], self.today())

    # ------------------------------------------------------------ packs and routes

    def install_pack(self, pack, trusted=False, builtin=False, trust_ids=()):
        pack = clean_pack(pack)  # idempotent: a pack that was already cleaned passes through unchanged
        now = self._now()
        stored = self._stored_packs()
        stored[pack['id']] = {k: pack[k] for k in ('id', 'name', 'short', 'author', 'note', 'colleges', 'portals')}
        stored[pack['id']]['builtin'] = builtin
        with self._tx() as db:
            for route in pack['routes']:
                old = db.execute('SELECT enabled, trusted, data FROM geese_routes WHERE id = ?', (route['id'],)).fetchone()
                trust = 1 if trusted or not route['script'] or route['id'] in trust_ids else 0
                if old and json.loads(old['data']).get('script') == route['script'] and old['trusted']:
                    trust = 1
                data = json.dumps(route, ensure_ascii=False)
                if old:
                    db.execute('UPDATE geese_routes SET pack = ?, data = ?, trusted = ? WHERE id = ?',
                               (pack['id'], data, trust, route['id']))
                else:
                    db.execute('INSERT INTO geese_routes (id, pack, data, enabled, trusted, added, next_fetch) '
                               'VALUES (?, ?, ?, 1, ?, ?, 0)', (route['id'], pack['id'], data, trust, now))
            if builtin:
                keep = [r['id'] for r in pack['routes']]
                db.execute(f'DELETE FROM geese_routes WHERE pack = ? AND id NOT IN ({",".join("?" * len(keep))})',
                           (pack['id'], *keep))
            db.execute('INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value',
                       ('geese_packs', json.dumps(stored, ensure_ascii=False)))
        self.packs[pack['id']] = dict(stored[pack['id']], routes=pack['routes'])
        return self.packs[pack['id']]

    def remove_pack(self, pid):
        stored = self._stored_packs()
        if (stored.get(pid) or {}).get('builtin'):
            raise ValueError('内置的驿路包不能移除，可以把不需要的驿路关掉')
        stored.pop(pid, None)
        with self._tx() as db:
            ids = [r[0] for r in db.execute('SELECT id FROM geese_routes WHERE pack = ?', (pid,)).fetchall()]
            for rid in ids:
                db.execute('DELETE FROM geese_letters WHERE route_id = ?', (rid,))
            db.execute('DELETE FROM geese_routes WHERE pack = ?', (pid,))
            db.execute('INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value',
                       ('geese_packs', json.dumps(stored, ensure_ascii=False)))
        self.packs.pop(pid, None)

    def preview_pack(self, raw):
        """Validate an imported pack and try its first route, so the user sees real notices before trusting it."""
        pack = clean_pack(raw)
        sample, error = [], ''
        first = next((r for r in pack['routes'] if not r['login']), None)
        if first:
            try:
                page = self.courier.get(first['url'])
                sample = extract_items(first, page)[0][:5]  # a script runs in the sandbox: safe to try before trusting
            except LoginNeeded:
                error = '这条驿路需要先登录门户'
            except Exception as error_:  # noqa: BLE001 - shown to the user as is
                error = _text(error_, 160)
        return {'pack': {k: pack[k] for k in ('id', 'name', 'author', 'note')},
                'routes': [{'id': r['id'], 'name': r['name'], 'column': r['column'], 'url': r['url'],
                            'script': r['script'], 'login': r['login']} for r in pack['routes']],
                'sample': sample, 'sample_route': first and first['name'], 'error': error,
                'exists': pack['id'] in self.packs}

    def _route(self, row):
        route = json.loads(row['data'])
        return dict(route, enabled=bool(row['enabled']), trusted=bool(row['trusted']), last_fetch=row['last_fetch'],
                    last_ok=row['last_ok'], next_fetch=row['next_fetch'], error=row['error'] or '', fails=row['fails'],
                    seen=bool(row['seen']))

    def routes(self, card=None):
        card = card or self.card() or default_card()
        out = []
        for row in self._rows('SELECT * FROM geese_routes ORDER BY pack, added, id'):
            route = self._route(row)
            route['active'], route['why'] = self._active(route, card)
            pack = self.packs.get(route['pack']) or {}
            route['pack_name'] = pack.get('name', route['pack'])
            route['pack_builtin'] = bool(pack.get('builtin'))
            if route['login']:
                route['portal'] = dict(self._portal(route) or {}, **self.sessions.status(route['login']))
            order = [r['id'] for r in pack.get('routes') or []]
            route['_order'] = order.index(route['id']) if route['id'] in order else len(order)
            out.append(route)
        out.sort(key=lambda r: (not r['pack_builtin'], r['pack'], r.pop('_order')))  # as the pack lists them
        return out

    def _active(self, route, card):
        if not route['enabled']:
            return False, '已关闭'
        if route['script'] and not route['trusted']:
            return False, '含脚本，等你确认信任'
        pack = self.packs.get(route['pack']) or {}
        if pack.get('builtin') and route['pack'] != card.get('school'):
            return False, '不是你的学校'
        if route['college'] and route['college'] != card.get('college'):
            return False, f'只给{route["college"]}的同学'
        if route['level'] and route['level'] != card.get('level'):
            return False, '只给本科生' if route['level'] == 'undergrad' else '只给研究生'
        return True, ''

    def _portal(self, route):
        pack = self.packs.get(route['pack']) or {}
        portal = (pack.get('portals') or {}).get(route['login'])
        if not portal:
            return None
        hosts = [urllib.parse.urlparse(portal['login']).hostname]
        return dict(portal, id=route['login'], login_hosts=hosts)

    def portals(self):
        out = {}
        for pack in self.packs.values():
            for key, portal in (pack.get('portals') or {}).items():
                out[key] = dict(portal, id=key, **self.sessions.status(key))
        return out

    def set_route(self, rid, data):
        row = self._row('SELECT * FROM geese_routes WHERE id = ?', (rid,))
        if not row:
            raise LookupError('没有这条驿路')
        fields = {}
        if 'enabled' in data:
            fields['enabled'] = 1 if data['enabled'] else 0
        if 'trusted' in data:
            fields['trusted'] = 1 if data['trusted'] else 0
        if fields:
            sets = ', '.join(f'{k} = ?' for k in fields)
            with self._tx() as db:
                db.execute(f'UPDATE geese_routes SET {sets} WHERE id = ?', (*fields.values(), rid))
        return next(r for r in self.routes() if r['id'] == rid)

    # ------------------------------------------------------------ fetching

    def due(self, now=None, card=None):
        card = card or self.card()
        if not card:
            return []
        now = now or self._now()
        routes = [r for r in self.routes(card) if r['active']]
        if card.get('mode') == 'morning':
            today = datetime.fromtimestamp(now)
            if today.hour < 6:
                return []
            start = datetime.combine(today.date(), datetime.min.time()).timestamp()
            return [r for r in routes if (r['last_fetch'] or 0) < start and (r['next_fetch'] or 0) <= now]
        return [r for r in routes if (r['next_fetch'] or 0) <= now]

    def fetch(self, routes=None, backfill=False, force=False, wait=False):
        """Fetch the given (or due) routes, one worker per school site. Returns the ids of new letters."""
        if not self._run_lock.acquire(timeout=180) if wait else not self._run_lock.acquire(blocking=False):
            raise RuntimeError('鸿雁已经在路上了')
        try:
            self.running = True
            card = self.card() or default_card()
            routes = routes if routes is not None else ([r for r in self.routes(card) if r['active']] if force else self.due())
            if not routes:
                return []
            by_host = {}
            for route in routes:
                by_host.setdefault(urllib.parse.urlparse(route['url']).hostname, []).append(route)
            self.progress = {'done': 0, 'total': len(routes), 'route': ''}
            self.publish('geese-progress', self.progress)
            new_ids = []
            with ThreadPoolExecutor(max_workers=min(6, len(by_host))) as pool:
                for ids in pool.map(lambda rs: self._fetch_host(rs, backfill, card), by_host.values()):
                    new_ids += ids
            return new_ids
        finally:
            self.running = False
            self.progress = None
            self._run_lock.release()

    def _fetch_host(self, routes, backfill, card):
        ids = []
        for route in routes:
            try:
                ids += self.fetch_route(route, backfill=backfill or not route['seen'], card=card)
            except Exception as error:  # noqa: BLE001 - one broken route never stops the others
                print(f'驿路「{route["name"]}」取信失败：{error}', file=sys.stderr, flush=True)
            if self.progress is not None:
                self.progress['done'] += 1
                self.progress['route'] = route['name']
                self.publish('geese-progress', dict(self.progress))
        return ids

    def fetch_route(self, route, backfill=False, card=None):
        now = self._now()
        sorter = self.sorter(card)
        portal = self._portal(route) if route['login'] else None
        try:
            pages, url = [], route['url']
            first = self.courier.get(url, None if backfill else self._route_etag(route['id']),
                                     None if backfill else self._route_modified(route['id']), portal)
            if first.not_modified:
                self._route_ok(route, now, None, None)
                return []
            pages.append(first)
            items, next_url = extract_items(route, first)
            cutoff = iso(self.today() - timedelta(days=BACKFILL_DAYS))
            while backfill and next_url and len(pages) < BACKFILL_PAGES and items and all(
                    (i['published'] or '9') >= cutoff for i in items[-3:]):
                try:  # older pages are a bonus: losing one never costs the first page
                    page = self.courier.get(next_url, portal=portal)
                    more, next_url = extract_items(route, page)
                except (OSError, ValueError):
                    break
                pages.append(page)
                items += more
        except LoginNeeded as error:
            self._route_failed(route, now, 'login', f'需要重新登录{error}')
            self.publish('geese-login', {'route': route['id'], 'portal': route['login']})
            return []
        except Exception as error:
            self._route_failed(route, now, 'error', _text(error, 200))
            raise
        items = [i for i in items if not i['published'] or i['published'] >= cutoff]
        recent = iso(self.today() - timedelta(days=FRESH_DAYS))
        known = {r['id'] for r in self._rows('SELECT id FROM geese_letters WHERE route_id = ?', (route['id'],))}
        fresh = [dict(i, id=letter_id(route['id'], i['link'])) for i in items]
        fresh = [i for i in fresh if i['id'] not in known]
        quiet_run = backfill or not route['seen']
        cap = BACKFILL_DETAIL_CAP if backfill else DETAIL_CAP
        rows = []
        for item in fresh:
            verdict = sorter.score(item['title'], item['summary'], route)
            detail = {}
            if cap > 0 and (verdict['score'] > 0 or (route['college'] and route['college'] == (card or {}).get('college'))):
                cap -= 1
                detail = self._detail(route, item['link'], portal)
            quiet = 1 if quiet_run or (item['published'] and item['published'] < recent) else 0
            rows.append(self._compose(route, item, detail, sorter, now, quiet))
        with self._tx() as db:
            for row in rows:
                db.execute(f'INSERT OR IGNORE INTO geese_letters ({", ".join(row)}) VALUES ({", ".join("?" * len(row))})',
                           tuple(row.values()))
        self._route_ok(route, now, first.etag, first.modified)
        return [r['id'] for r in rows]

    def _detail(self, route, link, portal):
        try:
            return extract_detail(route, self.courier.get(link, portal=portal))
        except LoginNeeded:
            raise
        except Exception as error:  # noqa: BLE001 - the list entry is still worth keeping
            return {'error': _text(error, 120)}

    def _compose(self, route, item, detail, sorter, now, quiet):
        published = item['published'] or detail.get('published') or ''
        body = detail.get('body') or ''
        verdict = sorter.score(item['title'], (item['summary'] + '\n' + body).strip(), route)
        when, clause = find_deadline(item['title'] + '\n' + item['summary'] + '\n' + body,
                                     date.fromisoformat(published) if published else self.today())
        return {'id': item['id'], 'route_id': route['id'], 'route_name': route['name'], 'title': item['title'],
                'link': item['link'], 'published': published, 'summary': item['summary'],
                'content': detail.get('content'), 'body': body,
                'attachments': json.dumps(detail.get('attachments') or [], ensure_ascii=False),
                'detail': 'ok' if detail.get('content') is not None else ('error' if detail.get('error') else 'none'),
                'fetched_at': now, 'score': verdict['score'], 'passed': int(verdict['passed']), 'cubby': verdict['cubby'],
                'reasons': json.dumps(verdict['reasons'], ensure_ascii=False), 'deadline': iso(when) if when else None,
                'deadline_text': clause, 'quiet': quiet}

    def _route_etag(self, rid):
        return (self._row('SELECT etag FROM geese_routes WHERE id = ?', (rid,)) or {}).get('etag')

    def _route_modified(self, rid):
        return (self._row('SELECT modified FROM geese_routes WHERE id = ?', (rid,)) or {}).get('modified')

    def _route_ok(self, route, now, etag, modified):
        with self._tx() as db:
            db.execute("""UPDATE geese_routes SET last_fetch = ?, last_ok = ?, next_fetch = ?, error = NULL, fails = 0,
                          seen = 1, etag = COALESCE(?, etag), modified = COALESCE(?, modified) WHERE id = ?""",
                       (now, now, now + route['interval'] * 60, etag, modified, route['id']))

    def _route_failed(self, route, now, kind, message):
        fails = (route.get('fails') or 0) + 1
        wait = min(route['interval'] * 60 * 2 ** min(fails, 6), 12 * 3600)
        with self._tx() as db:
            db.execute('UPDATE geese_routes SET last_fetch = ?, next_fetch = ?, error = ?, fails = ? WHERE id = ?',
                       (now, now + wait, f'{kind}:{message}', fails, route['id']))

    # ------------------------------------------------------------ sorting

    def rescore(self, card=None):
        """After the card changes: sort every letter again. Letters that now pass are not announced as new."""
        sorter = self.sorter(card)
        routes = {r['id']: r for r in self.routes(card)}
        rows = self._rows('SELECT id, route_id, title, summary, body, published, passed, feedback FROM geese_letters '
                          'WHERE archived_at IS NULL')
        with self._tx() as db:
            for row in rows:
                verdict = sorter.score(row['title'], (row['summary'] + '\n' + row['body']).strip(),
                                       routes.get(row['route_id']), row['feedback'])
                db.execute('UPDATE geese_letters SET score = ?, passed = ?, cubby = ?, reasons = ?, '
                           'quiet = CASE WHEN ? AND NOT passed THEN 1 ELSE quiet END WHERE id = ?',
                           (verdict['score'], int(verdict['passed']), verdict['cubby'],
                            json.dumps(verdict['reasons'], ensure_ascii=False), int(verdict['passed']), row['id']))
        return len(rows)

    def trial(self, data):
        """Sort the last month's notices with a card that is not saved yet: who would get through, and how many stay sealed."""
        card = clean_card(data)
        routes = [r for r in self.routes(card) if r['active']]
        missing = [r for r in routes if not r['seen']]
        if missing:
            self.fetch(missing, backfill=True, wait=True)
        sorter = self.sorter(card)
        by_route = {r['id']: r for r in routes}
        cutoff = iso(self.today() - timedelta(days=31))
        rows = self._rows(f"""SELECT id, route_id, route_name, title, summary, body, published, deadline FROM geese_letters
                              WHERE route_id IN ({",".join("?" * len(by_route)) or "''"}) AND (published >= ? OR published = '')
                              ORDER BY published DESC""", (*by_route, cutoff))
        kept, sealed = [], 0
        for row in rows:
            verdict = sorter.score(row['title'], (row['summary'] + '\n' + row['body']).strip(), by_route.get(row['route_id']))
            if verdict['passed']:
                kept.append({'id': row['id'], 'title': row['title'], 'route_name': row['route_name'],
                             'published': row['published'], 'deadline': row['deadline'], **verdict})
            else:
                sealed += 1
        kept.sort(key=lambda r: -r['score'])
        names = {c['id']: c['name'] for c in card['cares']}
        counts = {}
        for letter in kept:
            counts[letter['cubby']] = counts.get(letter['cubby'], 0) + 1
        return {'kept': kept[:40], 'kept_count': len(kept), 'sealed': sealed, 'total': len(rows),
                'cubbies': [{'id': k, 'name': names.get(k, '杂信'), 'count': v} for k, v in counts.items()],
                'routes': [{'id': r['id'], 'name': r['name'], 'column': r['column'], 'error': r['error']}
                           for r in self.routes(card) if r['active']]}

    # ------------------------------------------------------------ reading

    def _letter(self, row, full=False):
        item = dict(row)
        item['reasons'] = json.loads(item.get('reasons') or '[]')
        item['attachments'] = json.loads(item.get('attachments') or '[]')
        item['urgent'] = self._urgent(item)
        item['days_left'] = (date.fromisoformat(item['deadline']) - self.today()).days if item.get('deadline') else None
        if not full:
            for key in ('content', 'body'):
                item.pop(key, None)
            item['summary'] = (item.get('summary') or '')[:160]
        return item

    def _urgent(self, item):
        if not item.get('passed'):
            return False
        if item.get('score', 0) >= VERY:
            return True
        if item.get('deadline'):
            left = (date.fromisoformat(item['deadline']) - self.today()).days
            return 0 <= left <= URGENT_DAYS
        return False

    def cabinet(self):
        card = self.card()
        rows = self._rows("""SELECT * FROM geese_letters WHERE passed = 1 AND archived_at IS NULL
                             ORDER BY pinned DESC, read_at IS NOT NULL, published DESC, fetched_at DESC""")
        letters = [self._letter(r) for r in rows]
        cubbies = []
        for care in (card or {}).get('cares') or []:
            mine = [l for l in letters if l['cubby'] == care['id']]
            cubbies.append({'id': care['id'], 'name': care['name'], 'count': len(mine),
                            'unread': sum(1 for l in mine if not l['read_at']), 'urgent': sum(1 for l in mine if l['urgent'])})
        misc = [l for l in letters if l['cubby'] not in {c['id'] for c in cubbies}]
        cubbies.append({'id': 'misc', 'name': '杂信', 'count': len(misc), 'unread': sum(1 for l in misc if not l['read_at']),
                        'urgent': sum(1 for l in misc if l['urgent'])})
        for letter in misc:
            letter['cubby'] = 'misc'
        cutoff = self._now() - UNOPENED_DAYS * 86400
        unopened = self._row('SELECT COUNT(*) AS n FROM geese_letters WHERE passed = 0 AND archived_at IS NULL '
                             'AND fetched_at >= ?', (cutoff,))['n']
        archived = self._row('SELECT COUNT(*) AS n FROM geese_letters WHERE archived_at IS NOT NULL')['n']
        routes = self.routes(card)
        last = max((r['last_ok'] or 0 for r in routes), default=0)
        return {'card': card, 'cubbies': cubbies, 'letters': letters, 'unopened': unopened, 'archived': archived,
                'routes': [{'id': r['id'], 'name': r['name'], 'column': r['column'], 'active': r['active'],
                            'error': r['error'], 'last_ok': r['last_ok']} for r in routes if r['active']],
                'last_fetch': last or None, 'running': self.running, 'progress': self.progress,
                'presets': PRESET_CARES, 'portals': self.portals(), 'schools': self.schools()}

    def schools(self):
        """Packs that describe a school (with its colleges), for the card's first step."""
        return [{'id': p['id'], 'name': p['name'], 'short': p.get('short') or p['name'],
                 'colleges': [c['name'] for c in p.get('colleges') or []]}
                for p in self.packs.values() if p.get('builtin') or p.get('colleges')]

    def drawer(self, box, query='', limit=200):
        """The other boxes: 'unopened' (did not pass, kept 30 days) and 'archive' (old letters, searchable)."""
        if box == 'unopened':
            sql = 'SELECT * FROM geese_letters WHERE passed = 0 AND archived_at IS NULL AND fetched_at >= ?'
            args = [self._now() - UNOPENED_DAYS * 86400]
        elif box == 'archive':
            sql, args = 'SELECT * FROM geese_letters WHERE archived_at IS NOT NULL', []
        else:
            raise ValueError('未知的抽屉')
        if query:
            sql += ' AND (title LIKE ? OR body LIKE ? OR route_name LIKE ?)'
            args += [f'%{query}%'] * 3
        rows = self._rows(sql + ' ORDER BY published DESC, fetched_at DESC LIMIT ?', (*args, limit))
        return [self._letter(r) for r in rows]

    def letter(self, lid, open_it=True):
        row = self._row('SELECT * FROM geese_letters WHERE id = ?', (lid,))
        if not row:
            raise LookupError('这封信找不到了')
        if open_it and row['detail'] != 'ok':
            route = next((r for r in self.routes() if r['id'] == row['route_id']), None)
            if route:
                try:
                    detail = self._detail(route, row['link'], self._portal(route) if route['login'] else None)
                except LoginNeeded as error:
                    detail = {'error': f'需要重新登录{error}'}
                if detail.get('content') is not None:
                    item = {'id': lid, 'title': row['title'], 'link': row['link'], 'published': row['published'],
                            'summary': row['summary']}
                    fresh = self._compose(route, item, detail, self.sorter(), row['fetched_at'], row['quiet'])
                    with self._tx() as db:
                        db.execute("""UPDATE geese_letters SET content = ?, body = ?, attachments = ?, detail = 'ok',
                                      published = ?, deadline = COALESCE(deadline, ?), deadline_text = CASE
                                      WHEN deadline IS NULL THEN ? ELSE deadline_text END WHERE id = ?""",
                                   (fresh['content'], fresh['body'], fresh['attachments'], fresh['published'],
                                    fresh['deadline'], fresh['deadline_text'], lid))
                    row = self._row('SELECT * FROM geese_letters WHERE id = ?', (lid,))
                else:
                    row = dict(row, detail_error=detail.get('error', ''))
        if open_it and not row['read_at']:
            now = self._now()
            with self._tx() as db:
                db.execute('UPDATE geese_letters SET read_at = ? WHERE id = ?', (now, lid))
            row = dict(row, read_at=now)
        item = self._letter(row, full=True)
        item['highlights'] = self._highlights(item)
        return item

    def _highlights(self, item):
        words = [w for w in item['reasons'] if not w.startswith(('你说过', '不想看'))]
        card = self.card() or {}
        for care in card.get('cares') or []:
            if care['id'] == item.get('cubby'):
                words += [k for k in care['keywords'] if k in (item.get('body') or '') or k in item['title']]
        return sorted(set(w for w in words if len(w) >= 2), key=len, reverse=True)[:12]

    def update_letter(self, lid, data):
        row = self._row('SELECT * FROM geese_letters WHERE id = ?', (lid,))
        if not row:
            raise LookupError('这封信找不到了')
        fields = {}
        if 'read' in data:
            fields['read_at'] = (row['read_at'] or self._now()) if data['read'] else None
        if 'pinned' in data:
            fields['pinned'] = 1 if data['pinned'] else 0
            if data['pinned']:
                fields['archived_at'] = None
        if 'archived' in data:
            fields['archived_at'] = self._now() if data['archived'] else None
            if not data['archived'] and not row['passed']:
                fields['passed'] = 1
        for key in ('commission_id', 'appointment_id'):
            if key in data:
                fields[key] = str(data[key])[:40] if data[key] else None
        if fields:
            sets = ', '.join(f'{k} = ?' for k in fields)
            with self._tx() as db:
                db.execute(f'UPDATE geese_letters SET {sets} WHERE id = ?', (*fields.values(), lid))
        return self._letter(self._row('SELECT * FROM geese_letters WHERE id = ?', (lid,)))

    # ------------------------------------------------------------ teaching

    def words(self, lid):
        """Candidate words from a letter's title, for 「这封对我有用」 / 「以后别送这类」."""
        row = self._row('SELECT title, cubby FROM geese_letters WHERE id = ?', (lid,))
        if not row:
            raise LookupError('这封信找不到了')
        title = row['title']
        known = [k for c in PRESET_CARES for k in c['keywords'] if k in title]
        keys = sorted({k for c in PRESET_CARES for k in c['keywords']}, key=len, reverse=True)
        splitter = re.compile('|'.join(map(re.escape, keys + ['校内', '全国', '高校'])))
        chunks = []
        for chunk in STOP_WORDS.split(title):
            # A long run of characters is cut again at the words Violet already knows (竞赛, 选拔赛…).
            for piece in (splitter.split(chunk) if len(chunk) > 12 else [chunk]):
                if 2 <= len(piece) <= 12 and not piece.isdigit():
                    chunks.append(piece)
        card = self.card() or default_card()
        existing = {k for c in card['cares'] for k in c['keywords']} | set(card['avoid'])
        out = []
        for word in known + chunks:
            if word not in out and word not in existing:
                out.append(word)
        guess = next((c['id'] for c in card['cares'] if any(k in title for k in c['keywords'])), None)
        if not guess:
            guess = next((c['id'] for c in PRESET_CARES if any(k in title for k in c['keywords'])), None)
        return {'words': out[:10], 'guess': guess, 'title': title}

    def teach(self, lid, data):
        """Apply the user's correction: mark the letter, and only if they ticked words, write those into the card."""
        kind = data.get('kind')
        if kind not in ('useful', 'not'):
            raise ValueError('未知的纠错方式')
        if not self._row('SELECT 1 FROM geese_letters WHERE id = ?', (lid,)):
            raise LookupError('这封信找不到了')
        with self._tx() as db:
            db.execute('UPDATE geese_letters SET feedback = ?, quiet = 1 WHERE id = ?', (kind, lid))
        words = [_text(w, 20) for w in data.get('words') or [] if _text(w, 20)]
        card = self.card()
        if words and card:
            if kind == 'not':
                card['avoid'] = list(dict.fromkeys(card['avoid'] + words))
            else:
                target = data.get('care')
                care = next((c for c in card['cares'] if c['id'] == target), None)
                if care is None:
                    preset = next((c for c in PRESET_CARES if c['id'] == target), None)
                    if preset:
                        care = dict(preset, keywords=list(preset['keywords']))
                        card['cares'].append(care)
                    else:
                        name = _text(data.get('care_name') or words[0], 12)
                        care = {'id': 'c' + hashlib.sha1(name.encode()).hexdigest()[:6], 'name': name, 'keywords': []}
                        card['cares'].append(care)
                care['keywords'] = list(dict.fromkeys(care['keywords'] + words))
            self.save_card(card)
        else:
            self.rescore()
        return self.letter(lid, open_it=False)

    # ------------------------------------------------------------ upkeep, alerts and the daily letter

    def tidy(self):
        """Archive what has gone by, forget sealed letters after 30 days and old letters after a year."""
        now, today = self._now(), iso(self.today())
        with self._tx() as db:
            db.execute("""UPDATE geese_letters SET archived_at = ? WHERE archived_at IS NULL AND passed = 1 AND pinned = 0
                          AND ((deadline IS NOT NULL AND deadline < ?)
                               OR ((deadline IS NULL OR deadline < ?) AND fetched_at < ?))""",
                       (now, today, today, now - STALE_DAYS * 86400))
            db.execute('DELETE FROM geese_letters WHERE passed = 0 AND archived_at IS NULL AND pinned = 0 AND fetched_at < ?',
                       (now - UNOPENED_DAYS * 86400,))
            db.execute('DELETE FROM geese_letters WHERE archived_at IS NOT NULL AND pinned = 0 AND archived_at < ?',
                       (now - ARCHIVE_KEEP_DAYS * 86400,))

    def alerts(self, now=None):
        """Urgent letters to announce now: grouped into one notification, never between 23:00 and 7:00."""
        card = self.card()
        if not card or not card.get('urgent', True):
            return None
        now = now or self._now()
        hour = datetime.fromtimestamp(now).hour
        if hour >= QUIET_HOURS[0] or hour < QUIET_HOURS[1]:
            return None
        rows = self._rows("""SELECT * FROM geese_letters WHERE passed = 1 AND quiet = 0 AND notified = 0
                             AND archived_at IS NULL AND fetched_at >= ?""", (now - 86400,))
        urgent = [self._letter(r) for r in rows]
        urgent = [l for l in urgent if l['urgent']]
        with self._tx() as db:
            db.execute('UPDATE geese_letters SET notified = 1 WHERE passed = 1 AND quiet = 0 AND notified = 0 AND fetched_at >= ?',
                       (now - 86400,))
        if not urgent:
            return None
        urgent.sort(key=lambda l: (l['days_left'] if l['days_left'] is not None else 99, -l['score']))
        if len(urgent) == 1:
            letter = urgent[0]
            title = f'鸿雁 · {letter["route_name"]}'
            text = f'《{short_title(letter["title"], 30)}》' + _left_phrase(letter, '，')
        else:
            title = f'鸿雁带来 {len(urgent)} 封急件'
            text = '、'.join(f'《{short_title(l["title"], 16)}》' for l in urgent[:3]) + ('等' if len(urgent) > 3 else '')
        self.notify(title, text)
        return {'title': title, 'text': text, 'ids': [l['id'] for l in urgent]}

    def paragraph(self, day=None):
        """A paragraph for Violet's letter, written from the actual notices of the last day. None when there are none."""
        day = date.fromisoformat(day) if isinstance(day, str) else (day or self.today())
        start = datetime.combine(day - timedelta(days=1), datetime.min.time()).replace(hour=6).timestamp()
        end = datetime.combine(day, datetime.max.time()).timestamp()
        # New since yesterday morning; on the first day (a quiet batch) the notices published since yesterday.
        rows = self._rows("""SELECT * FROM geese_letters WHERE passed = 1 AND archived_at IS NULL
                             AND ((quiet = 0 AND fetched_at BETWEEN ? AND ?) OR (quiet = 1 AND published >= ?))
                             ORDER BY score DESC""", (start, end, iso(day - timedelta(days=1))))
        fresh = [self._letter(r) for r in rows]
        soon = [self._letter(r) for r in self._rows(
            """SELECT * FROM geese_letters WHERE passed = 1 AND archived_at IS NULL AND deadline BETWEEN ? AND ?
               AND commission_id IS NULL ORDER BY deadline""", (iso(day), iso(day + timedelta(days=URGENT_DAYS))))]
        soon = [l for l in soon if l['id'] not in {f['id'] for f in fresh}]
        if not fresh and not soon:
            return None
        parts = []
        if fresh:
            sources = list(dict.fromkeys(l['route_name'] for l in fresh))
            count = _count(len(fresh))
            where = f'，来自{"和".join(sources[:2])}{"等处" if len(sources) > 2 else ""}' if sources else ''
            parts.append(f'今天鸿雁送来{count}封学校的信{where}。')
            for letter in fresh[:2]:
                why = _why(letter)
                parts.append(f'{letter["route_name"]}那封《{_bare(letter)}》，{why}{_left_phrase(letter, "，")}。')
            if len(fresh) > 2:
                parts.append('另外几封，我替你夹在窗前的信绳上了。')
        soon = soon[:1] if len(fresh) >= 2 else soon[:2]
        if len(soon) == 1:
            parts.append(f'还有之前那封《{_bare(soon[0])}》{_left_phrase(soon[0], "")}，别忘了。')
        elif soon:
            parts.append(f'还有之前的《{_bare(soon[0])}》和《{_bare(soon[1])}》，'
                         f'{_when(soon[0])}和{_when(soon[1])}截止，别忘了。')
        return {'text': ''.join(parts), 'ids': [l['id'] for l in fresh[:2] + soon[:2]], 'count': len(fresh)}

    def due_on(self, day):
        rows = self._rows('SELECT * FROM geese_letters WHERE passed = 1 AND deadline = ? ORDER BY score DESC', (day,))
        return [self._letter(r) for r in rows]


def _bare(letter):
    """The title without its envelope, and without repeating who sent it."""
    title = letter['title']
    for name in (letter.get('route_name') or '', '西北工业大学'):
        if name and title.startswith(name) and len(title) > len(name) + 4:
            title = title[len(name):]
    return short_title(title)


def _when(letter):
    left = letter.get('days_left')
    return {0: '今天', 1: '明天', 2: '后天'}.get(left, f'{left} 天后')


def _count(n):
    return '一两三四五六七八九十'[n - 1] if 1 <= n <= 10 else str(n)  # 两封, not 二封


def _why(letter):
    reasons = [r for r in letter.get('reasons') or [] if not r.startswith(('你说过', '不想看'))]
    if not reasons:
        return '看着和你有关'
    return f'提到了{"、".join(reasons[:2])}'


def _left_phrase(letter, lead):
    left = letter.get('days_left')
    if left is None or left < 0:
        return ''
    when = date.fromisoformat(letter['deadline'])
    stamp = f'{when.month}月{when.day}日'
    if left == 0:
        return f'{lead}今天就截止'
    if left == 1:
        return f'{lead}明天（{stamp}）截止'
    if left == 2:
        return f'{lead}后天（{stamp}）截止'
    return f'{lead}{stamp}截止，还有{left}天'
