import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from violet_letters import Letters, Plays, load_quotes, parse_playlist_link, song_signature


class FakeLibrary:
    def __init__(self, tracks):
        self.tracks = tracks

    def list(self):
        return list(self.tracks)

    def scan(self, roots):
        return self.list()


def chart(songs):
    return lambda top_id: (songs, '2026-10-09')


class LetterTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.tracks = [{'id': f't{i}', 'title': f'旧歌{i}', 'artist': '歌手', 'album': '', 'mtime': i} for i in range(10)]
        self.plays = Plays(self.root / 'plays.json')
        self.songs = [{'platform': 'qq', 'id': f'm{i}', 'name': f'新歌{i}', 'artist': '某人', 'album': '', 'duration': 1000}
                      for i in range(8)]
        self.songs.append({'platform': 'qq', 'id': 'owned', 'name': '旧歌1（Live）', 'artist': '歌手', 'album': '',
                           'duration': 1})

    def letters(self, day='2026-10-11'):
        letters = Letters(FakeLibrary(self.tracks), self.plays, self.root / 'letters.json',
                          fetch=chart(self.songs), today=lambda: day)
        letters.fetch_quote = lambda: None
        return letters

    def test_one_letter_per_day_persisted(self):
        first = self.letters().today_letter()
        again = self.letters().today_letter()
        self.assertEqual(first['date'], '2026-10-11')
        self.assertEqual(first['quote'], again['quote'])
        self.assertEqual(len(json.loads((self.root / 'letters.json').read_text(encoding='utf-8'))), 1)
        self.assertFalse(first['opened'])

    def test_new_songs_skip_library_and_old_letter_prefers_unplayed(self):
        for track in self.tracks[:9]:
            self.plays.record(track['id'])
        letter = self.letters().today_letter()
        self.assertEqual(len(letter['songs']), 3)
        self.assertNotIn('owned', [s['id'] for s in letter['songs']])
        self.assertEqual(letter['old']['id'], 't9')

    def test_chart_failure_still_delivers_a_letter(self):
        letters = self.letters()
        letters.fetch_chart = lambda top_id: (_ for _ in ()).throw(OSError('offline'))
        letter = letters.today_letter()
        self.assertEqual(letter['songs'], [])
        self.assertIn('offline'[:0], letter['songs_error'])
        self.assertTrue(letter['quote']['text'])

    def test_new_songs_come_from_the_ticked_sources(self):
        letters = self.letters()
        netease = [{'platform': 'netease', 'id': f'n{i}', 'name': f'网易{i}', 'artist': '某人', 'album': '', 'duration': 1}
                   for i in range(6)]
        loved = [{'platform': 'netease', 'id': f'a{i}', 'name': f'歌手的歌{i}', 'artist': '歌手', 'album': '', 'duration': 1}
                 for i in range(6)] + [{'platform': 'netease', 'id': 'dup', 'name': '旧歌3', 'artist': '歌手', 'duration': 1}]
        asked = []
        letters.fetch_netease = lambda pid: asked.append(pid) or ('飙升榜', netease)
        letters.fetch_artist = lambda artist: asked.append(artist) or loved
        letters.sources = lambda: {'charts': ['netease:19723756'], 'taste': True, 'playlists': [], 'count': 4}
        letter = letters.today_letter()
        self.assertEqual(len(letter['songs']), 4)
        self.assertEqual({s['source'] for s in letter['songs']}, {'chart', 'taste'})
        self.assertNotIn('dup', [s['id'] for s in letter['songs']])  # already in the letter box
        self.assertIn('网易云「飙升榜」', letter['songs_intro'])
        self.assertIn('顺着你常听的歌手', letter['songs_intro'])
        self.assertIn('四首', letter['songs_intro'])

    def test_no_sources_ticked(self):
        letters = self.letters()
        letters.sources = lambda: {'charts': [], 'taste': False, 'playlists': [], 'count': 3}
        letter = letters.today_letter()
        self.assertEqual(letter['songs'], [])
        self.assertIn('没有勾选', letter['songs_error'])

    def test_playlist_links(self):
        self.assertEqual(parse_playlist_link('https://music.163.com/#/playlist?id=2884035'), ('netease', '2884035'))
        self.assertEqual(parse_playlist_link('https://y.qq.com/n/ryqq/playlist/9080103532'), ('qq', '9080103532'))
        with self.assertRaises(ValueError):
            parse_playlist_link('https://example.com/list/1')

    def test_open_and_star(self):
        letters = self.letters()
        letters.today_letter()
        self.assertTrue(letters.update('2026-10-11', opened=True, starred=True)['starred'])
        with self.assertRaises(LookupError):
            letters.update('1999-01-01', opened=True)

    def test_starred_letters_survive_the_limit(self):
        letters = self.letters()
        letters.letters = [{'date': f'd{i}', 'starred': False, 'quote': {}} for i in range(400)]
        letters.letters.append({'date': 'kept', 'starred': True, 'quote': {}})
        letters.today_letter()
        dates = [l['date'] for l in letters.letters]
        self.assertIn('kept', dates)
        self.assertNotIn('d399', dates)
        self.assertEqual(len([l for l in letters.letters if not l.get('starred')]), 400)

    def test_failed_save_is_reported_and_not_kept(self):
        letters = self.letters()
        letters.today_letter()
        with patch('violet_letters._write_json', side_effect=OSError(28, 'No space left on device')):
            with self.assertRaises(OSError):
                letters.update('2026-10-11', starred=True)
        self.assertFalse(letters.get('2026-10-11')['starred'])
        self.assertFalse(self.letters().get('2026-10-11')['starred'])

    def test_cold_start_scans_library_before_picking_new_songs(self):
        library = FakeLibrary(self.tracks)
        library.list = lambda: []  # nothing indexed yet, as on a fresh start
        library.scan = lambda roots: list(self.tracks)
        letters = Letters(library, self.plays, self.root / 'cold.json', fetch=chart(self.songs), today=lambda: '2026-10-11')
        letters.fetch_quote = lambda: None
        letter = letters.today_letter(['music'])
        self.assertNotIn('owned', [s['id'] for s in letter['songs']])
        self.assertTrue(letter['old'])

    def test_notes_come_from_the_desk(self):
        letters = self.letters()
        letters.context = lambda day: ['今天是霜降。', '']
        self.assertEqual(letters.today_letter()['notes'], ['今天是霜降。'])

    def test_quotes_are_attributed(self):
        quotes = load_quotes()
        self.assertGreater(len(quotes), 150)
        self.assertTrue(all(q['text'] and q['author'] for q in quotes))
        self.assertEqual(len({q['text'] for q in quotes}), len(quotes))

    def test_signature_ignores_version_suffixes(self):
        self.assertEqual(song_signature('晴天（Live）', '周杰伦/五月天'), song_signature('晴天', '周杰伦'))


if __name__ == '__main__':
    unittest.main()
