#!/usr/bin/env python3
"""生成 data/lunar.json：1900–2100 的农历月份表与二十四节气。

只用标准库，按天文算法推算：
- 朔日：Meeus《天文算法》第 49 章（含行星摄动项），ΔT 用 Espenak–Meeus 多项式，按东八区定日。
- 节气：2000–2099 用寿星通式（含已知修正年份，与紫金山天文台一致）；其余年份按太阳视黄经推算。
- 置闰：冬至所在月为十一月；两个冬至月之间有 13 个月时，第一个不含中气的月份为闰月。
ICU（浏览器内置的中国历）在朔时靠近午夜时会差一天（如 2027、2030 年春节），所以不用它。

  python tools/build_almanac.py
"""
from datetime import date, timedelta
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
J2000 = 2451545.0
UNIX_EPOCH_JD = 2440587.5
TZ_CHINA = 8 / 24

TERM_NAMES = ['小寒', '大寒', '立春', '雨水', '惊蛰', '春分', '清明', '谷雨', '立夏', '小满', '芒种', '夏至',
              '小暑', '大暑', '立秋', '处暑', '白露', '秋分', '寒露', '霜降', '立冬', '小雪', '大雪', '冬至']
TERM_C21 = [5.4055, 20.12, 3.87, 18.73, 5.63, 20.646, 4.81, 20.1, 5.52, 21.04, 5.678, 21.37,
            7.108, 22.83, 7.5, 23.13, 7.646, 23.042, 8.318, 23.438, 7.438, 22.36, 7.18, 21.94]
TERM_FIX = {(2026, '雨水'): -1, (2084, '春分'): 1, (2008, '小满'): 1, (2016, '小暑'): 1, (2002, '立秋'): 1,
            (2089, '霜降'): 1, (2089, '立冬'): 1, (2021, '冬至'): -1, (2019, '小寒'): -1, (2082, '大寒'): 1}


def sin(deg):
    return math.sin(math.radians(deg))


def delta_t(year):
    """Seconds between TT and UT (Espenak & Meeus polynomials)."""
    y = year
    if y < 1920:
        t = y - 1900
        return -2.79 + 1.494119 * t - 0.0598939 * t ** 2 + 0.0061966 * t ** 3 - 0.000197 * t ** 4
    if y < 1941:
        t = y - 1920
        return 21.20 + 0.84493 * t - 0.076100 * t ** 2 + 0.0020936 * t ** 3
    if y < 1961:
        t = y - 1950
        return 29.07 + 0.407 * t - t ** 2 / 233 + t ** 3 / 2547
    if y < 1986:
        t = y - 1975
        return 45.45 + 1.067 * t - t ** 2 / 260 - t ** 3 / 718
    if y < 2005:
        t = y - 2000
        return 63.86 + 0.3345 * t - 0.060374 * t ** 2 + 0.0017275 * t ** 3 + 0.000651814 * t ** 4 + 0.00002373599 * t ** 5
    if y < 2050:
        t = y - 2000
        return 62.92 + 0.32217 * t + 0.005589 * t ** 2
    u = (y - 1820) / 100
    return -20 + 32 * u ** 2 - 0.5628 * (2150 - y)


def new_moon_jde(k):
    """Julian Ephemeris Day of mean-phase index k (Meeus ch. 49, new moon)."""
    T = k / 1236.85
    jde = 2451550.09766 + 29.530588861 * k + 0.00015437 * T ** 2 - 0.000000150 * T ** 3 + 0.00000000073 * T ** 4
    E = 1 - 0.002516 * T - 0.0000074 * T ** 2
    M = 2.5534 + 29.10535670 * k - 0.0000014 * T ** 2 - 0.00000011 * T ** 3
    Mp = 201.5643 + 385.81693528 * k + 0.0107582 * T ** 2 + 0.00001238 * T ** 3 - 0.000000058 * T ** 4
    F = 160.7108 + 390.67050284 * k - 0.0016118 * T ** 2 - 0.00000227 * T ** 3 + 0.000000011 * T ** 4
    O = 124.7746 - 1.56375588 * k + 0.0020672 * T ** 2 + 0.00000215 * T ** 3
    jde += (-0.40720 * sin(Mp) + 0.17241 * E * sin(M) + 0.01608 * sin(2 * Mp) + 0.01039 * sin(2 * F)
            + 0.00739 * E * sin(Mp - M) - 0.00514 * E * sin(Mp + M) + 0.00208 * E * E * sin(2 * M)
            - 0.00111 * sin(Mp - 2 * F) - 0.00057 * sin(Mp + 2 * F) + 0.00056 * E * sin(2 * Mp + M)
            - 0.00042 * sin(3 * Mp) + 0.00042 * E * sin(M + 2 * F) + 0.00038 * E * sin(M - 2 * F)
            - 0.00024 * E * sin(2 * Mp - M) - 0.00017 * sin(O) - 0.00007 * sin(Mp + 2 * M)
            + 0.00004 * sin(2 * Mp - 2 * F) + 0.00004 * sin(3 * M) + 0.00003 * sin(Mp + M - 2 * F)
            + 0.00003 * sin(2 * Mp + 2 * F) - 0.00003 * sin(Mp + M + 2 * F) + 0.00003 * sin(Mp - M + 2 * F)
            - 0.00002 * sin(Mp - M - 2 * F) - 0.00002 * sin(3 * Mp + M) + 0.00002 * sin(4 * Mp))
    planetary = [(0.000325, 299.77 + 0.107408 * k - 0.009173 * T ** 2), (0.000165, 251.88 + 0.016321 * k),
                 (0.000164, 251.83 + 26.651886 * k), (0.000126, 349.42 + 36.412478 * k),
                 (0.000110, 84.66 + 18.206239 * k), (0.000062, 141.74 + 53.303771 * k),
                 (0.000060, 207.14 + 2.453732 * k), (0.000056, 154.84 + 7.306860 * k),
                 (0.000047, 34.52 + 27.261239 * k), (0.000042, 207.19 + 0.121824 * k),
                 (0.000040, 291.34 + 1.844379 * k), (0.000037, 161.72 + 24.198154 * k),
                 (0.000035, 239.56 + 25.513099 * k), (0.000023, 331.55 + 3.592518 * k)]
    return jde + sum(c * sin(a) for c, a in planetary)


def sun_longitude(jde):
    """Apparent solar longitude in degrees (Meeus ch. 25, ~0.01°)."""
    T = (jde - J2000) / 36525
    L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T ** 2
    M = 357.52911 + 35999.05029 * T - 0.0001537 * T ** 2
    C = ((1.914602 - 0.004817 * T - 0.000014 * T ** 2) * sin(M) + (0.019993 - 0.000101 * T) * sin(2 * M)
         + 0.000289 * sin(3 * M))
    omega = 125.04 - 1934.136 * T
    return (L0 + C - 0.00569 - 0.00478 * sin(omega)) % 360


def jd_to_china_date(jd_ut):
    return date(1970, 1, 1) + timedelta(days=math.floor(jd_ut + TZ_CHINA - UNIX_EPOCH_JD))


def date_to_jd(day):
    return (day - date(1970, 1, 1)).days + UNIX_EPOCH_JD


def term_by_astronomy(year, index):
    """Date (China) when the sun reaches the index-th term of the calendar year (0 = 小寒 at 285°)."""
    target = (285 + 15 * index) % 360
    month = index // 2 + 1
    guess = date_to_jd(date(year, month, 5 if index % 2 == 0 else 20))
    jde = guess
    for _ in range(50):
        diff = (target - sun_longitude(jde) + 180) % 360 - 180
        jde += diff / 360 * 365.2422
        if abs(diff) < 1e-7:
            break
    return jd_to_china_date(jde - delta_t(year) / 86400)


def solar_terms(year):
    if 2000 <= year <= 2099:
        y = year % 100
        out = []
        for index, (name, c) in enumerate(zip(TERM_NAMES, TERM_C21)):
            leap_days = (y - 1) // 4 if index < 4 else y // 4
            day = int(y * 0.2422 + c) - leap_days + TERM_FIX.get((year, name), 0)
            out.append(date(year, index // 2 + 1, day))
        return out
    return [term_by_astronomy(year, i) for i in range(24)]


def new_moons(first_year, last_year):
    k = math.floor((first_year - 2000) * 12.3685) - 2
    out = []
    while True:
        jde = new_moon_jde(k)
        day = jd_to_china_date(jde - delta_t(2000 + (jde - J2000) / 365.25) / 86400)
        if day.year > last_year:
            return out
        out.append(day)
        k += 1


def build(first=1900, last=2100):
    moons = new_moons(first - 1, last + 1)
    terms = {y: solar_terms(y) for y in range(first - 1, last + 2)}
    # Principal terms (中气): the odd indexes, 大寒 雨水 … 冬至.
    zhongqi = sorted(d for y in terms for i, d in enumerate(terms[y]) if i % 2 == 1)

    def month_index(day):
        """Index of the lunar month (by its first day) that contains day."""
        lo = 0
        for i, start in enumerate(moons):
            if start <= day:
                lo = i
            else:
                break
        return lo

    numbered = {}  # month start -> (number, leap)
    for year in range(first - 1, last + 1):
        a = month_index(terms[year][23])        # month holding this year's 冬至: month 11
        b = month_index(terms[year + 1][23])    # next 冬至 month
        leap_needed = b - a == 13
        number, leap_used = 11, False
        for i in range(a, b):
            start, end = moons[i], moons[i + 1]
            has_zhongqi = any(start <= z < end for z in zhongqi)
            if i == a:
                numbered[start] = (11, False)
                continue
            if leap_needed and not leap_used and not has_zhongqi:
                numbered[start] = (number, True)
                leap_used = True
                continue
            number = number % 12 + 1
            numbered[start] = (number, False)

    years = {}
    starts = sorted(numbered)
    for i, start in enumerate(starts[:-1]):
        number, leap = numbered[start]
        length = (starts[i + 1] - start).days
        if number == 1 and not leap:
            years[start.year] = [start.isoformat(), []]
        # Attach the month to the lunar year that began most recently.
        current = max((y for y in years if date.fromisoformat(years[y][0]) <= start), default=None)
        if current is not None:
            years[current][1].append(-length if leap else length)
    years = {y: v for y, v in years.items() if first <= y <= last and len(v[1]) in (12, 13)}
    term_table = {y: [(d - date(y, 1, 1)).days for d in terms[y]] for y in range(first, last + 1)}
    return years, term_table


def main():
    years, terms = build()
    target = ROOT / 'data' / 'lunar.json'
    target.write_text(json.dumps({'years': years, 'terms': terms}, separators=(',', ':')), encoding='utf-8')
    print(f'data/lunar.json · {len(years)} 个农历年 · {len(terms)} 年节气')


if __name__ == '__main__':
    main()
