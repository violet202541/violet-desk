from datetime import date, datetime, timedelta
from pathlib import Path
import tempfile
import unittest

import violet_almanac as almanac
from violet_desk import Conflict, Desk, next_occurrence


class Clock:
    def __init__(self, day):
        self.now = datetime.combine(day, datetime.min.time()).timestamp() + 10 * 3600

    def __call__(self):
        return self.now


class DeskTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.day = date(2026, 10, 10)  # a Saturday, 九月初一
        self.clock = Clock(self.day)
        self.desk = Desk(Path(self.folder.name) / 'desk.db', today=lambda: self.day, clock=self.clock)
        self.addCleanup(self.desk.close)

    def test_stationery_is_kept_with_the_reply(self):
        reply = self.desk.create_reply({'body': '你好', 'stationery': {'paper': 'kraft', 'font': 'xiaolai', 'evil': 'x',
                                                                        'ink': '<script>'}})
        self.assertEqual(reply['stationery'], {'paper': 'kraft', 'font': 'xiaolai'})
        sealed = self.desk.seal_reply(reply['id'], revision=reply['revision'],
                                      stationery={'paper': 'lilac-laid', 'signoff': '你的   小满', 'seal_initials': 'ABCD'})
        self.assertEqual(sealed['stationery'], {'paper': 'lilac-laid', 'font': 'xiaolai', 'signoff': '你的 小满',
                                                'seal_initials': 'ABC'})

    def test_desk_looks_a_week_ahead(self):
        for title, days in (('昨天的', -1), ('今天的', 0), ('明天的', 1), ('周五的', 6), ('一周后', 7), ('远的', 8), ('更远', 30)):
            self.desk.create_commission({'title': title, 'due_date': (self.day + timedelta(days=days)).isoformat()})
        view = self.desk.today_view()
        self.assertEqual([c['title'] for c in view['commissions']], ['昨天的', '今天的'])
        self.assertEqual([c['title'] for c in view['upcoming']], ['明天的', '周五的', '一周后'])
        self.assertEqual(view['later'], 2)

    def test_commission_numbers_and_revision_conflict(self):
        a = self.desk.create_commission({'title': '整理照片', 'client': '自己', 'due_date': '2026-10-10'})
        b = self.desk.create_commission({'title': '交论文初稿'})
        self.assertEqual((a['number'], b['number']), (1, 2))
        updated = self.desk.update_commission(a['id'], {'title': '整理旅行照片', 'revision': a['revision']})
        self.assertEqual(updated['revision'], 2)
        with self.assertRaises(Conflict) as caught:
            self.desk.update_commission(a['id'], {'title': '旧标题', 'revision': a['revision']})
        self.assertEqual(caught.exception.current['title'], '整理旅行照片')
        with self.assertRaises(ValueError):
            self.desk.create_commission({'title': '  '})

    def test_repeating_commission_spawns_next_and_undo_takes_it_back(self):
        item = self.desk.create_commission({'title': '背单词', 'due_date': '2026-10-07', 'repeat': {'freq': 'daily'},
                                            'steps': ['新词', '复习']})
        done, spawned = self.desk.complete_commission(item['id'])
        self.assertEqual(done['status'], 'done')
        # Completed late: the next one lands on today, not in the past.
        self.assertEqual(spawned['due_date'], '2026-10-10')
        self.assertEqual([s['done'] for s in spawned['steps']], [False, False])
        reopened, _ = self.desk.complete_commission(item['id'], done=False)
        self.assertEqual(reopened['status'], 'open')
        self.assertIsNone(self.desk.commission(spawned['id']))

    def test_next_occurrence_rules(self):
        friday = date(2026, 10, 9)
        self.assertEqual(next_occurrence(friday, {'freq': 'weekly', 'interval': 1, 'weekdays': [0, 2]}), date(2026, 10, 12))
        self.assertEqual(next_occurrence(date(2026, 10, 12), {'freq': 'weekly', 'interval': 2, 'weekdays': [0, 2]}),
                         date(2026, 10, 14))
        self.assertEqual(next_occurrence(date(2026, 10, 14), {'freq': 'weekly', 'interval': 2, 'weekdays': [0, 2]}),
                         date(2026, 10, 26))
        self.assertEqual(next_occurrence(date(2026, 1, 31), {'freq': 'monthly', 'interval': 1}), date(2026, 2, 28))
        self.assertEqual(next_occurrence(date(2028, 2, 29), {'freq': 'yearly', 'interval': 1}), date(2029, 2, 28))

    def test_lunar_anniversary_repeats_on_lunar_date(self):
        # Born on 八月十五 2000 (2000-09-12): the birthday follows the moon every year.
        self.desk.create_appointment({'kind': 'anniversary', 'title': '妈妈生日', 'date': '2000-09-12', 'lunar': True})
        found = self.desk.occurrences('2026-09-01', '2026-10-31')
        self.assertEqual([(o['title'], o['on'], o['years']) for o in found], [('妈妈生日', '2026-09-25', 26)])
        self.assertEqual(almanac.lunar('2026-09-25')['day_name'], '十五')

    def test_future_letter_travels_until_its_day(self):
        reply = self.desk.create_reply({'body': '一年后的我，你好。', 'mood': 'calm'})
        self.assertEqual(reply['state'], 'draft')
        with self.assertRaises(ValueError):
            self.desk.seal_reply(reply['id'], 'future', '2026-10-10')
        sealed = self.desk.seal_reply(reply['id'], 'future', '2027-10-10', revision=reply['revision'])
        self.assertEqual(sealed['state'], 'travelling')
        with self.assertRaises(ValueError):
            self.desk.update_reply(reply['id'], {'body': '改一改'})
        self.assertEqual(self.desk.arrivals(), [])
        self.assertEqual([r['id'] for r in self.desk.arrivals(date(2027, 10, 10))], [reply['id']])

    def test_reply_attaches_commissions_done_that_day(self):
        task = self.desk.create_commission({'title': '寄出申请', 'due_date': '2026-10-10'})
        self.desk.complete_commission(task['id'])
        reply = self.desk.create_reply({'body': '今天寄出了申请。'})
        sealed = self.desk.seal_reply(reply['id'])
        self.assertEqual([c['title'] for c in sealed['commissions']], ['寄出申请'])
        self.assertEqual(sealed['state'], 'sealed')

    def test_letter_notes_mention_what_matters(self):
        self.desk.create_commission({'title': '还书', 'due_date': '2026-10-08'})
        self.desk.create_commission({'title': '买花', 'due_date': '2026-10-10'})
        self.desk.create_appointment({'title': '和朋友吃饭', 'date': '2026-10-10', 'start': '18:30'})
        self.desk.create_appointment({'kind': 'anniversary', 'title': '纪念日', 'date': '2020-10-12'})
        notes = self.desk.letter_notes(self.day)
        text = '\n'.join(notes)
        self.assertIn('「还书」', text)
        self.assertIn('今天有 1 份委托', text)
        self.assertIn('18:30', text)
        self.assertIn('再过 2 天就是「纪念日」', text)

    def test_reminders_fire_once_and_skip_stale(self):
        self.desk.create_commission({'title': '开会', 'due_date': '2026-10-10', 'due_time': '10:30', 'remind': 30})
        self.desk.create_commission({'title': '很久以前', 'due_date': '2026-10-01', 'due_time': '08:00', 'remind': 0})
        fired = self.desk.due_reminders(self.clock.now)
        self.assertEqual([f['title'] for f in fired], ['开会'])
        self.assertEqual(self.desk.due_reminders(self.clock.now + 60), [])

    def test_month_view_and_day_detail(self):
        task = self.desk.create_commission({'title': '洗衣服', 'due_date': '2026-10-10'})
        self.desk.complete_commission(task['id'])
        self.desk.record_listen({'id': 't1', 'title': '晴天', 'artist': '周杰伦'})
        self.desk.record_listen({'id': 't1', 'title': '晴天', 'artist': '周杰伦'})
        days = {d['date']: d for d in self.desk.month(2026, 10)}
        self.assertEqual(len(days), 42)
        self.assertEqual(days['2026-10-10']['done'], 1)
        self.assertEqual(days['2026-10-10']['listens'], 2)
        self.assertEqual(days['2026-10-08']['term'], '寒露')
        detail = self.desk.day('2026-10-10')
        self.assertEqual(detail['listens'][0]['count'], 2)

    def test_weekly_seal_freezes_summary(self):
        task = self.desk.create_commission({'title': '跑步', 'due_date': '2026-10-10'})
        self.desk.complete_commission(task['id'])
        week = self.desk.weekly('2026-W41')
        self.assertEqual([d['title'] for d in week['summary']['done']], ['跑步'])
        sealed = self.desk.seal_week('2026-W41', '这一周很充实')
        self.assertTrue(sealed['sealed_at'])
        self.assertEqual(sealed['note'], '这一周很充实')
        self.assertEqual(len(self.desk.sealed_weeks()), 1)
        with self.assertRaises(ValueError):
            self.desk.seal_week('2027-W01')

    def test_trash_is_purged_after_thirty_days(self):
        task = self.desk.create_commission({'title': '撕掉的委托'})
        self.desk.delete('commissions', task['id'])
        self.assertEqual(self.desk.commissions(), [])
        self.desk.delete('commissions', task['id'], restore=True)
        self.assertEqual(len(self.desk.commissions()), 1)
        self.desk.delete('commissions', task['id'])
        self.clock.now += 31 * 86400
        self.desk.purge_trash()
        self.assertIsNone(self.desk.commission(task['id']))


class AlmanacTests(unittest.TestCase):
    def test_spring_festivals_match_the_official_calendar(self):
        for day in ('2025-01-29', '2026-02-17', '2027-02-06', '2030-02-03'):
            info = almanac.lunar(day)
            self.assertEqual((info['month'], info['day'], info['leap']), (1, 1, False), day)
        self.assertEqual(almanac.festivals('2027-02-05'), ['除夕'])

    def test_terms_and_leap_months(self):
        self.assertEqual(almanac.solar_term('2026-02-18'), '雨水')
        self.assertEqual(almanac.lunar('2025-07-25')['month_name'], '闰六月')
        self.assertEqual(almanac.lunar_to_solar(2025, 6, 1, leap=True), date(2025, 7, 25))
        self.assertEqual(almanac.describe('2026-10-10')['label'], '九月')

    def test_pentads_follow_the_terms(self):
        self.assertEqual(len(almanac.PENTADS), 72)
        self.assertEqual(almanac.season('2026-10-10')['hou'], '鸿雁来宾')
        self.assertEqual(almanac.season('2026-10-18')['hou'], '菊有黄华')
        # Early January still belongs to the previous year's winter solstice.
        early = almanac.season('2026-01-03')
        self.assertEqual((early['term'], early['since']), ('冬至', '2025-12-21'))
        self.assertEqual(almanac.describe('2026-10-10', with_season=True)['season']['term'], '寒露')


if __name__ == '__main__':
    unittest.main()
