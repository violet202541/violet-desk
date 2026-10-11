from datetime import date, datetime
import json
import os
from pathlib import Path
import tempfile
import unittest

from violet_desk import Desk
from violet_letters import Letters, Plays
import violet_geese as geese
from violet_geese import (Geese, LoginNeeded, Page, RouteError, Sorter, clean_card, clean_pack, extract_detail,
                          extract_items, find_deadline, parse_date, run_script)

LIST_HTML = """<html><body><div class="list"><ul>
<li><a href="../info/1164/29998.htm">关于2027年国际大学生数学建模竞赛选拔报名的通知</a><span>2026-10-09</span></li>
<li><a href="../info/1164/30128.htm">教室电子时钟全面检修项目竞选结果公告</a><span>2026-10-09</span></li>
<li><a href="../info/1164/30200.htm">关于组织博士研究生开题公开答辩的通知</a><span>2026-10-08</span></li>
<li><a href="../info/1164/30300.htm">关于开展2024级本科生学籍信息自查的通知</a><span>2026-10-07</span></li>
<li><a href="../info/1164/30400.htm">图书馆闭馆通知</a><span>2026-10-06</span></li>
</ul></div><div class="p_next"><a href="tzgg/76.htm">下页</a></div></body></html>"""

DETAIL_HTML = """<html><body><div class="v_news_content">
<p>各学院：</p><p>竞赛将于北京时间2027年1月29日至2月2日举行。</p>
<p>3.报名截止日期：2026年10月11日（周日）晚20:00。</p>
<script>alert(1)</script><p onclick="x()">报名请联系<a href="javascript:evil()">这里</a>或<a href="/doc/a.htm">指南</a></p>
<img src="poster.png"></div>
<ul><li><a href="/system/_content/download.jsp?wbfileid=1">附件1-报名表.xlsx</a></li></ul></body></html>"""

PACK = {
    'format': 'violet-routes/1', 'id': 'nwpu', 'name': '西北工业大学',
    'colleges': [{'name': '动力与能源学院', 'aliases': ['动力与能源学院', '动能学院']},
                 {'name': '航空学院', 'aliases': ['航空学院']}],
    'portals': {'ecampus': {'name': '翱翔门户', 'login': 'https://uis.example.edu/cas/login',
                            'done': '^https://ecampus\\.example\\.edu/', 'hosts': ['ecampus.example.edu']}},
    'routes': [
        {'id': 'jw', 'name': '教务部', 'column': '通知公告', 'url': 'https://jw.example.edu/jxxx/tzgg.htm', 'interval': 60,
         'list': {'item': '.list li', 'title': 'a', 'link': 'a@href', 'date': 'span', 'next': '.p_next a@href'},
         'detail': {'content': '.v_news_content'}},
        {'id': 'dn', 'name': '动力与能源学院', 'column': '学院通知', 'college': '动力与能源学院',
         'url': 'https://dn.example.edu/tzgg.htm', 'list': {'item': '.list li'}},
        {'id': 'portal', 'name': '翱翔门户', 'url': 'https://ecampus.example.edu/api/notices', 'type': 'json',
         'login': 'ecampus', 'list': {'items': 'data.rows', 'title': 'title', 'link_template': 'https://ecampus.example.edu/n/{id}'}},
    ],
}


class FakeCourier:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, etag=None, modified=None, portal=None):
        self.calls.append(url)
        if portal:
            raise LoginNeeded(portal['name'])
        if url not in self.pages:
            raise OSError(f'404 {url}')
        return Page(url, 200, self.pages[url])


class ParsingTests(unittest.TestCase):
    def test_dates_in_the_shapes_school_sites_use(self):
        self.assertEqual(parse_date('2026-10-09'), date(2026, 10, 9))
        self.assertEqual(parse_date('2026/05/06&nbsp;'), date(2026, 5, 6))
        self.assertEqual(parse_date('发布时间：2026年9月28日'), date(2026, 9, 28))
        self.assertEqual(parse_date('08.26\n 2026'), date(2026, 8, 26))
        self.assertEqual(parse_date('10月9日', date(2026, 10, 10)), date(2026, 10, 9))
        self.assertIsNone(parse_date('今天'))

    def test_deadline_comes_from_a_clause_that_says_so(self):
        text = '竞赛将于北京时间2027年1月29日至2月2日举行。报名截止日期：2026年10月11日（周日）晚20:00。'
        self.assertEqual(find_deadline(text, date(2026, 9, 28))[0], date(2026, 10, 11))
        self.assertEqual(find_deadline('报名时间：10月1日至10月11日', date(2026, 9, 28))[0], date(2026, 10, 11))
        self.assertEqual(find_deadline('请于10月20日（周二）17:00前提交材料', date(2026, 10, 9))[0], date(2026, 10, 20))
        self.assertEqual(find_deadline('请于1月5日前提交', date(2026, 12, 20))[0], date(2027, 1, 5))
        self.assertIsNone(find_deadline('讲座于2026年10月20日举行。', date(2026, 10, 9))[0])

    def test_list_items_selectors_next_page_and_dropped_dates(self):
        route = clean_pack(PACK)['routes'][0]
        items, nxt = extract_items(route, Page('https://jw.example.edu/jxxx/tzgg.htm', 200, LIST_HTML))
        self.assertEqual(len(items), 5)
        self.assertEqual(items[0]['link'], 'https://jw.example.edu/info/1164/29998.htm')
        self.assertEqual(items[0]['published'], '2026-10-09')
        self.assertEqual(nxt, 'https://jw.example.edu/jxxx/tzgg/76.htm')
        dropped = clean_pack({**PACK, 'routes': [{**PACK['routes'][1], 'list': {
            'item': 'li', 'title': 'a', 'date': 'a span', 'drop': 'a span'}}]})['routes'][0]
        html = '<ul><li><a href="/i/1.htm">图书出版项目竞选结果公告<span>2026-09-14</span></a></li></ul>'
        item = extract_items(dropped, Page('https://dn.example.edu/tzgg.htm', 200, html))[0][0]
        self.assertEqual((item['title'], item['published']), ('图书出版项目竞选结果公告', '2026-09-14'))

    def test_detail_is_sanitized_and_keeps_attachments(self):
        route = clean_pack(PACK)['routes'][0]
        detail = extract_detail(route, Page('https://jw.example.edu/info/1164/29998.htm', 200, DETAIL_HTML))
        self.assertNotIn('script', detail['content'])
        self.assertNotIn('onclick', detail['content'])
        self.assertNotIn('javascript:', detail['content'])
        self.assertIn('href="https://jw.example.edu/doc/a.htm"', detail['content'])
        self.assertIn('原网页里可以看到', detail['content'])
        self.assertEqual(detail['attachments'][0]['name'], '附件1-报名表.xlsx')
        self.assertIn('2026年10月11日', detail['body'])

    def test_json_and_rss_routes(self):
        route = clean_pack(PACK)['routes'][2]
        body = json.dumps({'data': {'rows': [{'id': 7, 'title': '选课通知', 'date': '2026-10-01'}]}})
        items, _ = extract_items(route, Page('https://ecampus.example.edu/api/notices', 200, body))
        self.assertEqual(items[0]['link'], 'https://ecampus.example.edu/n/7')
        rss = clean_pack({**PACK, 'portals': {}, 'routes': [{'id': 'feed', 'name': '订阅', 'type': 'rss', 'url': 'https://x.edu/feed'}]})
        xml = ('<rss><channel><item><title>讲座预告</title><link>https://x.edu/1</link>'
               '<pubDate>Fri, 09 Oct 2026 08:00:00 +0800</pubDate><description>&lt;p&gt;周五&lt;/p&gt;</description></item>'
               '</channel></rss>')
        item = extract_items(rss['routes'][0], Page('https://x.edu/feed', 200, xml))[0][0]
        self.assertEqual((item['title'], item['published'], item['summary']), ('讲座预告', '2026-10-09', '周五'))

    def test_pack_validation_explains_what_is_wrong(self):
        with self.assertRaisesRegex(RouteError, 'violet-routes'):
            clean_pack({'id': 'x', 'routes': []})
        with self.assertRaisesRegex(RouteError, 'list.item'):
            clean_pack({**PACK, 'routes': [{'id': 'a1', 'name': 'A', 'url': 'https://a.edu/'}]})
        with self.assertRaisesRegex(RouteError, '门户'):
            clean_pack({**PACK, 'portals': {}})
        with self.assertRaisesRegex(RouteError, 'http'):
            clean_pack({**PACK, 'routes': [{'id': 'a1', 'name': 'A', 'url': 'file:///c:/', 'list': {'item': 'li'}}]})


class ScriptTests(unittest.TestCase):
    def test_script_turns_a_page_into_items(self):
        source = """function list(page) {
            var rows = json(page.body).rows; return rows.map(function (r) { return {title: text(r.t), link: r.u} })
        }"""
        found = run_script(source, 'list', {'url': 'https://x.edu/', 'body': '{"rows":[{"t":"<b>讲座</b>","u":"/1"}]}'})
        self.assertEqual(found, [{'title': '讲座', 'link': '/1'}])
        self.assertIsNone(run_script('var a = 1', 'detail', {'url': '', 'body': ''}))

    def test_script_has_no_way_out_and_cannot_run_forever(self):
        for source in ('function list(p) { return [typeof fetch, typeof XMLHttpRequest, typeof require, typeof std] }',):
            self.assertEqual(run_script(source, 'list', {}), ['undefined'] * 4)
        with self.assertRaisesRegex(RouteError, '脚本'):
            run_script('function list(p) { while (true) {} }', 'list', {})


class SorterTests(unittest.TestCase):
    def setUp(self):
        card = clean_card({'college': '动力与能源学院', 'entry_year': 2024, 'level': 'undergrad',
                           'cares': [c for c in geese.PRESET_CARES if c['id'] in ('contest', 'aid', 'course')]})
        self.sorter = Sorter(card, clean_pack(PACK)['colleges'], date(2026, 10, 10))

    def test_relevant_notices_pass_with_reasons(self):
        verdict = self.sorter.score('关于2027年国际大学生数学建模竞赛选拔报名的通知')
        self.assertTrue(verdict['passed'])
        self.assertEqual(verdict['cubby'], 'contest')
        self.assertIn('数学建模', verdict['reasons'])
        grade = self.sorter.score('关于开展2024级本科生学籍信息自查的通知')
        self.assertTrue(grade['passed'])
        self.assertIn('2024级', grade['reasons'])

    def test_noise_other_colleges_and_other_levels_stay_sealed(self):
        self.assertFalse(self.sorter.score('教室电子时钟全面检修项目竞选结果公告')['passed'])
        self.assertFalse(self.sorter.score('关于组织博士研究生开题公开答辩的通知')['passed'])
        self.assertFalse(self.sorter.score('航空学院2026年奖学金评审结果公示')['passed'])
        self.assertTrue(self.sorter.score('动能学院2026年奖学金评审结果公示')['passed'])
        self.assertIn('不想看：采购', self.sorter.score('学生月饼采购项目竞赛选拔公告')['reasons'])

    def test_own_college_route_counts_and_feedback_wins(self):
        route = {'college': '动力与能源学院'}
        verdict = self.sorter.score('关于发放暑假短期交流项目学院资助的通知', route=route)
        self.assertTrue(verdict['passed'])
        self.assertIn('动力与能源学院的通知', verdict['reasons'])
        self.assertTrue(self.sorter.score('图书馆闭馆通知', feedback='useful')['passed'])
        self.assertFalse(self.sorter.score('数学建模竞赛', feedback='not')['passed'])


class GeeseStoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.day = date(2026, 10, 10)
        self.now = datetime.combine(self.day, datetime.min.time()).timestamp() + 10 * 3600
        self.desk = Desk(Path(self.folder.name) / 'desk.db', today=lambda: self.day, clock=lambda: self.now)
        self.addCleanup(self.desk.close)
        self.pages = {
            'https://jw.example.edu/jxxx/tzgg.htm': LIST_HTML,
            'https://jw.example.edu/info/1164/29998.htm': DETAIL_HTML,
            'https://dn.example.edu/tzgg.htm': '<div class="list"><li><a href="/a.htm">学院奖学金评选通知</a></li></div>',
            'https://dn.example.edu/a.htm': '<div class="v_news_content">请于10月12日前提交。</div>',
        }
        for page in ('30128', '30200', '30300', '30400'):
            self.pages[f'https://jw.example.edu/info/1164/{page}.htm'] = '<div class="v_news_content">正文</div>'
        self.courier = FakeCourier(self.pages)
        self.notes = []
        old = geese.PACK_DIR
        geese.PACK_DIR = Path(self.folder.name) / 'none'
        self.addCleanup(setattr, geese, 'PACK_DIR', old)
        self.geese = Geese(self.desk, self.folder.name, courier=self.courier, today=lambda: self.day,
                           notify=lambda t, x: self.notes.append((t, x)))
        self.geese.install_pack(PACK, trusted=True)
        self.card = {'college': '动力与能源学院', 'entry_year': 2024,
                     'cares': [c for c in geese.PRESET_CARES if c['id'] in ('contest', 'aid', 'course')]}

    def test_routes_follow_the_card(self):
        self.geese.save_card({**self.card, 'college': '航空学院'})
        active = {r['id']: (r['active'], r['why']) for r in self.geese.routes()}
        self.assertTrue(active['jw'][0])
        self.assertEqual(active['dn'], (False, '只给动力与能源学院的同学'))
        self.geese.save_card(self.card)
        self.assertTrue(next(r for r in self.geese.routes() if r['id'] == 'dn')['active'])

    def test_first_fetch_is_quiet_and_sorts_into_cubbies(self):
        self.geese.save_card(self.card)
        new = self.geese.fetch(force=True)
        self.assertEqual(len(new), 6)
        cabinet = self.geese.cabinet()
        counts = {c['id']: c['count'] for c in cabinet['cubbies']}
        self.assertEqual(counts['contest'], 1)
        self.assertEqual(counts['aid'], 1)
        self.assertEqual(counts['course'], 1)
        self.assertEqual(cabinet['unopened'], 3)
        contest = next(l for l in cabinet['letters'] if l['cubby'] == 'contest')
        self.assertEqual((contest['deadline'], contest['days_left'], contest['urgent']), ('2026-10-11', 1, True))
        self.assertIsNone(self.geese.alerts())  # the first batch never pings
        self.assertEqual(self.notes, [])
        # The portal route needs a login and says so instead of failing silently.
        portal = next(r for r in self.geese.routes() if r['id'] == 'portal')
        self.assertTrue(portal['error'].startswith('login:'))

    def test_later_urgent_letters_are_announced_once_and_never_at_night(self):
        self.geese.save_card(self.card)
        self.geese.fetch(force=True)
        self.pages['https://jw.example.edu/jxxx/tzgg.htm'] = LIST_HTML.replace(
            '<ul>', '<ul><li><a href="../info/1164/31000.htm">关于大学生创新创业大赛报名的通知</a><span>2026-10-10</span></li>')
        self.pages['https://jw.example.edu/info/1164/31000.htm'] = '<div class="v_news_content">报名截止：10月12日。</div>'
        self.geese.fetch(force=True)
        night = datetime.combine(self.day, datetime.min.time()).timestamp() + 23.5 * 3600
        self.assertIsNone(self.geese.alerts(night))
        alert = self.geese.alerts()
        self.assertEqual(alert['title'], '鸿雁 · 教务部')
        self.assertIn('后天', alert['text'])
        self.assertIsNone(self.geese.alerts())

    def test_old_notices_never_arrive_as_new(self):
        self.geese.save_card(self.card)
        self.geese.fetch(force=True)
        self.pages['https://jw.example.edu/jxxx/tzgg.htm'] = LIST_HTML.replace('<ul>', (
            '<ul><li><a href="../info/1164/32000.htm">数学建模竞赛培训安排</a><span>2026-10-01</span></li>'
            '<li><a href="../info/1164/33000.htm">数学建模竞赛往届回顾</a><span>2026-08-01</span></li>'))
        self.geese.fetch(force=True)
        titles = {r['title']: r['quiet'] for r in self.desk._rows('SELECT title, quiet FROM geese_letters')}
        self.assertEqual(titles['数学建模竞赛培训安排'], 1)  # a week old: filed quietly, never announced
        self.assertNotIn('数学建模竞赛往届回顾', titles)  # older than the backfill window: dropped
        self.assertIsNone(self.geese.alerts())

    def test_daily_paragraph_is_written_from_the_actual_notices(self):
        self.assertIsNone(self.geese.paragraph(self.day))
        self.geese.save_card(self.card)
        self.geese.fetch(force=True)
        paragraph = self.geese.paragraph(self.day)
        self.assertIn('鸿雁送来', paragraph['text'])
        self.assertIn('国际大学生数学建模竞赛选拔报名', paragraph['text'])
        self.assertIn('明天（10月11日）截止', paragraph['text'])
        letters = Letters(None, Plays(Path(self.folder.name) / 'plays.json'), Path(self.folder.name) / 'letters.json')
        letters.geese = self.geese.paragraph
        self.assertEqual(letters._geese('2026-10-10')['count'], paragraph['count'])

    def test_opening_teaching_pinning_and_tidying(self):
        self.geese.save_card(self.card)
        self.geese.fetch(force=True)
        sealed = self.geese.drawer('unopened')
        closed = next(l for l in sealed if l['title'] == '图书馆闭馆通知')
        words = self.geese.words(closed['id'])
        self.assertIn('图书馆闭馆', words['words'])
        self.geese.teach(closed['id'], {'kind': 'useful', 'words': ['图书馆'], 'care': 'library', 'care_name': '图书馆'})
        card = self.geese.card()
        self.assertIn('图书馆', [c['name'] for c in card['cares']])
        self.assertIn(closed['id'], [l['id'] for l in self.geese.cabinet()['letters']])
        opened = self.geese.letter(closed['id'])
        self.assertTrue(opened['read_at'])
        contest = next(l for l in self.geese.cabinet()['letters'] if l['cubby'] == 'contest')
        self.geese.update_letter(contest['id'], {'pinned': True, 'commission_id': 'c1'})
        self.now += 20 * 86400
        self.day = date(2026, 10, 30)
        self.geese.tidy()
        left = [l['id'] for l in self.geese.cabinet()['letters']]
        self.assertEqual(left, [contest['id']])  # pinned under the paperweight; the rest went to the archive
        self.assertTrue(self.geese.drawer('archive', '闭馆'))

    def test_trial_sorts_last_month_with_an_unsaved_card(self):
        result = self.geese.trial(self.card)
        self.assertEqual(result['kept_count'], 3)
        self.assertEqual(result['sealed'], 3)
        self.assertIsNone(self.geese.card())

    def test_untrusted_scripts_wait_for_the_user(self):
        pack = {**PACK, 'id': 'mine', 'portals': {}, 'routes': [
            {'id': 'scripted', 'name': '脚本驿路', 'url': 'https://s.edu/', 'script': 'function list(p) { return [] }'}]}
        self.geese.install_pack(pack)
        route = next(r for r in self.geese.routes() if r['id'] == 'scripted')
        self.assertEqual((route['active'], route['why']), (False, '含脚本，等你确认信任'))
        self.geese.set_route('scripted', {'trusted': True})
        self.assertTrue(next(r for r in self.geese.routes() if r['id'] == 'scripted')['active'])
        self.geese.remove_pack('mine')
        self.assertFalse([r for r in self.geese.routes() if r['id'] == 'scripted'])


@unittest.skipUnless(os.name == 'nt', 'DPAPI is Windows only')
class SessionTests(unittest.TestCase):
    def test_sessions_are_encrypted_at_rest(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sessions.bin'
            sessions = geese.Sessions(path)
            sessions.save('ecampus', [{'name': 'SESSION', 'value': 'abc123', 'domain': '.ecampus.example.edu'}])
            self.assertNotIn(b'abc123', path.read_bytes())
            again = geese.Sessions(path)
            self.assertEqual(again.cookie_header('ecampus', 'ecampus.example.edu'), 'SESSION=abc123')
            self.assertEqual(again.cookie_header('ecampus', 'other.edu'), '')
            again.forget('ecampus')
            self.assertFalse(geese.Sessions(path).status('ecampus')['signed_in'])


if __name__ == '__main__':
    unittest.main()
