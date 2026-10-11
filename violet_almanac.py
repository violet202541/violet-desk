"""黄历小抄：农历、二十四节气与传统节日，供邮戳簿和每日来信使用。

数据来自 data/lunar.json（tools/build_almanac.py 按天文算法生成，覆盖 1900–2100）：
农历月份按东八区朔日与中气置闰；节气 2000–2099 年用寿星通式加修正年份，与紫金山天文台历表一致。
"""
from datetime import date, timedelta
from functools import lru_cache
import json
from pathlib import Path
import sys

if getattr(sys, 'frozen', False):
    DATA_DIR = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)) / 'data'
else:
    DATA_DIR = Path(__file__).resolve().parent / 'data'

MONTH_NAMES = ['正月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '冬月', '腊月']
DAY_NAMES = ['初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
             '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
             '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十']
STEMS = '甲乙丙丁戊己庚辛壬癸'
BRANCHES = '子丑寅卯辰巳午未申酉戌亥'
ZODIAC = '鼠牛虎兔龙蛇马羊猴鸡狗猪'

TERM_NAMES = ['小寒', '大寒', '立春', '雨水', '惊蛰', '春分', '清明', '谷雨', '立夏', '小满', '芒种', '夏至',
              '小暑', '大暑', '立秋', '处暑', '白露', '秋分', '寒露', '霜降', '立冬', '小雪', '大雪', '冬至']

# 七十二候：每个节气分三候，每候约五天（《逸周书·时训解》），后面是白话。顺序与 TERM_NAMES 一致。
PENTADS = [
    ('雁北乡', '大雁开始往北飞回故乡'), ('鹊始巢', '喜鹊开始筑巢'), ('雉始雊', '野鸡开始鸣叫'),
    ('鸡始乳', '母鸡开始孵小鸡'), ('征鸟厉疾', '鹰隼盘旋，捕食迅猛'), ('水泽腹坚', '湖泽的冰冻到最厚'),
    ('东风解冻', '东风吹来，冰雪消融'), ('蛰虫始振', '冬眠的虫子开始苏醒'), ('鱼陟负冰', '鱼游上水面，背着碎冰'),
    ('獭祭鱼', '水獭把捕到的鱼摆在岸边'), ('候雁北', '大雁北归'), ('草木萌动', '草木开始发芽'),
    ('桃始华', '桃花开了'), ('仓庚鸣', '黄鹂开始鸣叫'), ('鹰化为鸠', '鹰少了，布谷鸟多了起来'),
    ('玄鸟至', '燕子飞回来了'), ('雷乃发声', '开始打雷'), ('始电', '天上有了闪电'),
    ('桐始华', '泡桐开花'), ('田鼠化为鴽', '田鼠躲回洞里，鹌鹑出来了'), ('虹始见', '雨后开始见到彩虹'),
    ('萍始生', '浮萍开始生长'), ('鸣鸠拂其羽', '布谷鸟梳理羽毛，催人播种'), ('戴胜降于桑', '戴胜鸟落在桑树上'),
    ('蝼蝈鸣', '蝼蛄在田间鸣叫'), ('蚯蚓出', '蚯蚓钻出地面'), ('王瓜生', '王瓜的藤蔓长起来了'),
    ('苦菜秀', '苦菜长得茂盛'), ('靡草死', '喜阴的细草枯了'), ('麦秋至', '麦子快要成熟'),
    ('螳螂生', '小螳螂破壳而出'), ('鵙始鸣', '伯劳鸟开始鸣叫'), ('反舌无声', '爱学舌的百舌鸟安静了'),
    ('鹿角解', '鹿角开始脱落'), ('蜩始鸣', '知了开始叫'), ('半夏生', '半夏在水边长出来'),
    ('温风至', '吹来的风都是热的'), ('蟋蟀居壁', '蟋蟀躲到墙角避暑'), ('鹰始挚', '小鹰开始学习搏击'),
    ('腐草为萤', '草丛里飞出萤火虫'), ('土润溽暑', '土地潮湿，天气闷热'), ('大雨时行', '时常下大雨'),
    ('凉风至', '开始刮凉风'), ('白露降', '清晨有了露水'), ('寒蝉鸣', '寒蝉开始鸣叫'),
    ('鹰乃祭鸟', '鹰捕鸟储食'), ('天地始肃', '天地间开始萧瑟'), ('禾乃登', '庄稼成熟了'),
    ('鸿雁来', '大雁从北方飞来'), ('玄鸟归', '燕子南归'), ('群鸟养羞', '鸟儿储存过冬的食物'),
    ('雷始收声', '雷声渐渐停了'), ('蛰虫坯户', '虫子封好洞口准备过冬'), ('水始涸', '河湖的水开始变少'),
    ('鸿雁来宾', '最后一批大雁南来，像晚到的客人'), ('雀入大水为蛤', '雀鸟少了，海边多了蛤蜊'), ('菊有黄华', '菊花开了'),
    ('豺乃祭兽', '豺捕猎储食'), ('草木黄落', '草木枯黄落叶'), ('蛰虫咸俯', '虫子都蛰伏不动了'),
    ('水始冰', '水开始结冰'), ('地始冻', '土地开始冻结'), ('雉入大水为蜃', '野鸡少了，海边多了大蛤'),
    ('虹藏不见', '彩虹不再出现'), ('天气上升地气下降', '天地之气不再交通'), ('闭塞而成冬', '万物闭藏，进入寒冬'),
    ('鹖鴠不鸣', '寒号鸟也不叫了'), ('虎始交', '老虎开始求偶'), ('荔挺出', '马蔺草抽出新芽'),
    ('蚯蚓结', '蚯蚓在土里蜷成一团'), ('麋角解', '麋鹿脱角'), ('水泉动', '山泉开始流动'),
]

SOLAR_FESTIVALS = {(1, 1): '元旦', (2, 14): '情人节', (3, 8): '妇女节', (3, 12): '植树节', (4, 1): '愚人节',
                   (5, 1): '劳动节', (5, 4): '青年节', (6, 1): '儿童节', (7, 1): '建党节', (8, 1): '建军节',
                   (9, 10): '教师节', (10, 1): '国庆节', (12, 24): '平安夜', (12, 25): '圣诞节'}
LUNAR_FESTIVALS = {(1, 1): '春节', (1, 15): '元宵节', (2, 2): '龙抬头', (5, 5): '端午节', (7, 7): '七夕',
                   (7, 15): '中元节', (8, 15): '中秋节', (9, 9): '重阳节', (12, 8): '腊八节', (12, 23): '小年'}


@lru_cache(maxsize=1)
def _data():
    return json.loads((DATA_DIR / 'lunar.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def _table():
    return {int(year): (date.fromisoformat(start), months) for year, (start, months) in _data()['years'].items()}


def to_date(value):
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def lunar(day):
    """Chinese calendar date: dict(year, month 1–12, leap, day, month_name, day_name, ganzhi, zodiac) or None."""
    day = to_date(day)
    table = _table()
    year = day.year if day >= table.get(day.year, (date.max,))[0] else day.year - 1
    if year not in table:
        return None
    start, months = table[year]
    offset = (day - start).days
    number = 0
    for length in months:
        leap = length < 0
        if not leap:
            number += 1
        length = abs(length)
        if offset < length:
            return {'year': year, 'month': number, 'leap': leap, 'day': offset + 1,
                    'month_name': ('闰' if leap else '') + MONTH_NAMES[number - 1], 'day_name': DAY_NAMES[offset],
                    'ganzhi': STEMS[(year - 4) % 10] + BRANCHES[(year - 4) % 12], 'zodiac': ZODIAC[(year - 4) % 12]}
        offset -= length
    return None


def lunar_to_solar(year, month, day, leap=False):
    """The Gregorian date of a lunar date, or None (e.g. a 30th in a short month)."""
    table = _table()
    if year not in table:
        return None
    start, months = table[year]
    offset, number = 0, 0
    for length in months:
        is_leap = length < 0
        if not is_leap:
            number += 1
        if number == month and is_leap == leap:
            return start + timedelta(days=offset + day - 1) if day <= abs(length) else None
        offset += abs(length)
    return None


@lru_cache(maxsize=256)
def solar_terms(year):
    """{date: name} for the 24 terms of a Gregorian year."""
    offsets = _data()['terms'].get(str(year)) or []
    return {date(year, 1, 1) + timedelta(days=offset): name for name, offset in zip(TERM_NAMES, offsets)}


def solar_term(day):
    day = to_date(day)
    return solar_terms(day.year).get(day)


def season(day):
    """The solar-term period a day falls in, and which of its three pentads (候)."""
    day = to_date(day)
    terms = {**solar_terms(day.year - 1), **solar_terms(day.year)}
    starts = sorted(d for d in terms if d <= day)
    if not starts:
        return None
    start = starts[-1]
    name = terms[start]
    index = min(2, (day - start).days // 5)
    hou, gloss = PENTADS[TERM_NAMES.index(name) * 3 + index]
    return {'term': name, 'since': start.isoformat(), 'index': index, 'hou': hou, 'gloss': gloss}


def festivals(day, info=None):
    day = to_date(day)
    names = []
    if (day.month, day.day) in SOLAR_FESTIVALS:
        names.append(SOLAR_FESTIVALS[(day.month, day.day)])
    info = info or lunar(day)
    if info and not info['leap']:
        name = LUNAR_FESTIVALS.get((info['month'], info['day']))
        if name:
            names.insert(0, name)
        tomorrow = lunar(day + timedelta(days=1))
        if tomorrow and tomorrow['month'] == 1 and tomorrow['day'] == 1 and not tomorrow['leap']:
            names.insert(0, '除夕')
    if solar_term(day) == '清明':
        names.append('清明节')
    # Mother's Day and Father's Day: second Sunday of May, third Sunday of June.
    if day.weekday() == 6 and ((day.month == 5 and 8 <= day.day <= 14) or (day.month == 6 and 15 <= day.day <= 21)):
        names.append('母亲节' if day.month == 5 else '父亲节')
    return names


def describe(day, with_season=False):
    """Everything the stamp book shows under a date."""
    day = to_date(day)
    info = lunar(day)
    term = solar_term(day)
    names = festivals(day, info)
    label = term or (names[0] if names else '')
    if not label and info:
        label = info['month_name'] if info['day'] == 1 else info['day_name']
    out = {'date': day.isoformat(), 'lunar': info, 'term': term, 'festivals': names, 'label': label}
    if with_season:
        out['season'] = season(day)
    return out
