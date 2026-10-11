from datetime import date, datetime
from pathlib import Path
import tempfile
import unittest

from violet_desk import Conflict, Desk
from violet_letters import Letters, Plays
from violet_shelf import Shelf, song_key


def track(tid, title, artist='Violet', cover=True):
    return {'id': tid, 'title': title, 'artist': artist, 'album': '书信', 'has_cover': cover, 'duration': 200000,
            'mtime': 0}


class ShelfTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.day = date(2026, 10, 10)
        self.now = datetime.combine(self.day, datetime.min.time()).timestamp() + 36000
        self.desk = Desk(Path(self.folder.name) / 'desk.db', today=lambda: self.day, clock=lambda: self.now)
        self.addCleanup(self.desk.close)
        self.shelf = Shelf(self.desk)
        self.tracks = {t['id']: t for t in (track('a1', 'Sincerely'), track('b2', 'みちしるべ', '茅原実里'),
                                             track('c3', '晴天', '周杰伦', cover=False))}

    def test_song_key_ignores_case_spacing_and_featured_artists(self):
        self.assertEqual(song_key('Come Alive', 'Hugh Jackman / Keala Settle'), song_key('come  alive', 'HUGH JACKMAN'))
        self.assertNotEqual(song_key('晴天', '周杰伦'), song_key('晴天', '孙燕姿'))

    def test_press_and_unpress(self):
        self.shelf.press(self.tracks['a1'], '第一次听是在雨天')
        self.shelf.press(self.tracks['a1'])  # pressing again keeps the note
        pressed = self.shelf.pressed(self.tracks)
        self.assertEqual([(p['track_id'], p['note'], p['day']) for p in pressed], [('a1', '第一次听是在雨天', '2026-10-10')])
        self.assertEqual(self.shelf.pressed_days(self.day, self.day), {'2026-10-10': 1})
        self.shelf.unpress('a1')
        self.assertEqual(self.shelf.pressed_ids(), [])

    def test_bundle_add_dedupes_removes_and_reorders(self):
        bundle = self.shelf.create_bundle({'name': '雨天读的信', 'epigraph': '窗外在下雨', 'ribbon': 'prussian'})
        result = self.shelf.add(bundle['id'], [self.tracks['a1'], self.tracks['b2'], self.tracks['a1']], self.tracks)
        self.assertEqual((result['added'], result['duplicates']), (2, 1))
        self.assertEqual(result['bundle']['covers'], ['a1', 'b2'])
        letters = result['bundle']['letters']
        moved = self.shelf.reorder(bundle['id'], [letters[1]['id'], letters[0]['id']], self.tracks)
        self.assertEqual([l['title'] for l in moved['letters']], ['みちしるべ', 'Sincerely'])
        removed = self.shelf.remove(bundle['id'], [letters[0]['id']], self.tracks)
        self.assertEqual(removed['bundle']['count'], 1)
        # Putting a removed letter back keeps its old place.
        back = self.shelf.add(bundle['id'], removed['removed'], self.tracks)['bundle']
        self.assertEqual([l['title'] for l in back['letters']], ['みちしるべ', 'Sincerely'])
        self.assertEqual(self.shelf.all_memberships()['a1'], [bundle['id']])

    def test_moved_file_is_recognised_by_title_and_artist(self):
        bundle = self.shelf.create_bundle({'name': '旧唱片'})
        self.shelf.add(bundle['id'], [self.tracks['c3']], self.tracks)
        self.shelf.press(self.tracks['c3'])
        # The file moved: same song, new library id.
        moved = {'z9': dict(self.tracks['c3'], id='z9')}
        letters = self.shelf.bundle(bundle['id'], moved)['letters']
        self.assertEqual((letters[0]['state'], letters[0]['track_id']), ('here', 'z9'))
        self.assertEqual([p['state'] for p in self.shelf.pressed(moved)], ['here'])
        self.assertEqual(self.shelf.pressed_ids(), ['z9'])
        # Gone altogether: still listed, marked lost, never silently dropped.
        self.assertEqual(self.shelf.bundle(bundle['id'], {})['letters'][0]['state'], 'lost')

    def test_pending_songs_are_claimed_once_downloaded(self):
        bundle = self.shelf.create_bundle({'name': '抄来的歌单'})
        self.shelf.add(bundle['id'], [{'title': 'Sincerely', 'artist': 'TRUE'}], {})
        self.assertEqual(self.shelf.bundle(bundle['id'], {})['pending'], 1)
        arrived = {'n1': track('n1', 'Sincerely', 'TRUE')}
        claimed = self.shelf.bundle(bundle['id'], arrived)
        self.assertEqual((claimed['pending'], claimed['here'], claimed['letters'][0]['track_id']), (0, 1, 'n1'))

    def test_bundle_validation_conflict_and_restore(self):
        with self.assertRaises(ValueError):
            self.shelf.create_bundle({'name': ''})
        with self.assertRaises(ValueError):
            self.shelf.create_bundle({'name': '缎带', 'ribbon': 'neon'})
        bundle = self.shelf.create_bundle({'name': '初稿'})
        self.shelf.update_bundle(bundle['id'], {'name': '定稿', 'revision': bundle['revision']})
        with self.assertRaises(Conflict):
            self.shelf.update_bundle(bundle['id'], {'name': '旧的', 'revision': bundle['revision']})
        self.shelf.delete_bundle(bundle['id'])
        self.assertEqual(self.shelf.bundles(self.tracks), [])
        self.shelf.delete_bundle(bundle['id'], restore=True)
        self.assertEqual(self.shelf.bundles(self.tracks)[0]['name'], '定稿')

    def test_pressed_songs_reach_the_letter_and_the_week(self):
        self.now -= 365 * 86400
        self.day = date(2025, 10, 10)
        self.shelf.press(self.tracks['b2'])
        self.now += 365 * 86400
        self.day = date(2026, 10, 10)
        notes = self.desk.letter_notes('2026-10-10')
        self.assertIn('一年前的今天，你把《みちしるべ》压进了书里。', notes)
        self.shelf.press(self.tracks['a1'])
        summary = self.desk.week_summary('2026-W41')
        self.assertEqual([p['title'] for p in summary['pressed']], ['Sincerely'])

    def test_old_letter_prefers_a_pressed_song(self):
        plays = Plays(Path(self.folder.name) / 'plays.json')

        class Lib:
            tracks = self.tracks

        letters = Letters(Lib(), plays, Path(self.folder.name) / 'letters.json')
        letters.favored = lambda: {'b2'}
        import random
        picks = {letters._old_letter(random.Random(seed), [], list(self.tracks.values()))['id'] for seed in range(40)}
        self.assertIn('b2', picks)
        old = letters._old_letter(random.Random(1), [], [self.tracks['b2']])
        self.assertTrue(old['pressed'])


if __name__ == '__main__':
    unittest.main()
