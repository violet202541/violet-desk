import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import chksz_dl as dl
import violet_core as core
from violet_core import DownloadManager, EventBus, History, KeyStore, Settings


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    raise AssertionError('condition not reached')


def song(i, platform='netease', **extra):
    return {'platform': platform, 'id': str(i), 'name': f'歌{i}', 'artist': '歌手', 'album': '专辑', **extra}


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.bus = EventBus()
        self.history = History(self.root / 'history.json')
        self.manager = DownloadManager(self.bus, self.history)
        self.addCleanup(lambda: wait_until(lambda: self.manager.running == 0))
        self.addCleanup(self.manager.shutdown)
        self.settings = Settings(out_dir=str(self.root / 'music'), qualities={'netease': 'lossless', 'qq': 'flac', 'kugou': 'flac'})
        self.gate = threading.Event()
        self.started = []
        self.resolve = Mock(side_effect=lambda key, sid, level: {'url': f'https://cdn.test/{sid}.flac', 'level': level})

        def stream(url, path, progress=None, cancel=None):
            self.started.append(path)
            while not self.gate.wait(0.01):
                dl.check_cancel(cancel)
            dl.check_cancel(cancel)
            if progress:
                progress(4, 4)
            Path(path).write_bytes(b'flac')
            return 4

        patches = [patch.dict(dl.RESOLVE, {'netease': self.resolve, 'qq': self.resolve, 'kugou': self.resolve}),
                   patch('violet_core.stream_download', side_effect=stream),
                   patch('violet_core.embed_song_data', return_value='内嵌歌词 +内嵌封面')]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def states(self):
        return [job.state for job in self.manager.jobs]

    def test_bounded_concurrency_dedup_and_snapshot(self):
        added, dup = self.manager.enqueue([song(i) for i in range(6)], self.settings, 'chksz_a')
        self.assertEqual((len(added), dup), (6, 0))
        wait_until(lambda: len(self.started) == 4)
        time.sleep(0.05)
        self.assertEqual(len(self.started), 4, 'never more than four downloads at once')
        self.assertEqual(self.states().count('queued'), 2)

        # Changing settings later must not affect queued jobs; duplicates are refused.
        self.settings.qualities['netease'] = 'standard'
        _, dup = self.manager.enqueue([song(0), song(1)], self.settings, 'chksz_a')
        self.assertEqual(dup, 2)
        self.assertEqual(self.manager.jobs[5].settings.qualities['netease'], 'lossless')

        self.gate.set()
        wait_until(lambda: all(s == 'done' for s in self.states()) and len(self.history.records) == 6)
        self.assertTrue(all(Path(job.path).is_file() for job in self.manager.jobs))
        self.assertEqual(self.manager.jobs[0].flags, '内嵌歌词 +内嵌封面')

    def test_cancel_queued_and_running(self):
        self.manager.enqueue([song(i) for i in range(5)], self.settings, 'chksz_a')
        wait_until(lambda: len(self.started) == 4)
        self.assertEqual(self.manager.cancel(), 5)
        wait_until(lambda: all(s == 'cancelled' for s in self.states()) and len(self.history.records) == 5)
        wait_until(lambda: self.manager.running == 0)
        self.assertEqual(list((self.root / 'music').glob('*')), [])

    def test_existing_file_is_skipped_without_download(self):
        folder = self.root / 'music'
        folder.mkdir()
        (folder / '歌手 - 歌1.flac').write_bytes(b'original')
        self.gate.set()
        self.manager.enqueue([song(1)], self.settings, 'chksz_a')
        wait_until(lambda: self.states() == ['skipped'])
        self.assertEqual((folder / '歌手 - 歌1.flac').read_bytes(), b'original')
        self.assertEqual(self.started, [])

    def test_subfolders_and_phone_layout(self):
        self.gate.set()
        phone = Settings(out_dir=str(self.root / 'music'), ios=True)
        self.manager.enqueue([song(1)], phone, 'chksz_a')
        wait_until(lambda: self.states() == ['done'])
        self.assertTrue((self.root / 'music' / '歌手' / '专辑' / '歌手 - 歌1.flac').is_file())

    def test_auth_error_does_not_degrade_quality_but_404_does(self):
        self.gate.set()
        self.resolve.side_effect = dl.ApiError('invalid key', 401)
        self.manager.enqueue([song(1)], self.settings, 'chksz_a')
        wait_until(lambda: self.states() == ['failed'])
        self.assertEqual(self.resolve.call_count, 1)

        self.resolve.reset_mock()
        levels = []

        def only_standard(key, sid, level):
            levels.append(level)
            if level != 'standard':
                raise dl.ApiError('no such quality', 404)
            return {'url': 'https://cdn.test/a.mp3', 'level': level}

        self.resolve.side_effect = only_standard
        self.manager.enqueue([song(2)], self.settings, 'chksz_a')
        wait_until(lambda: self.manager.jobs[-1].state == 'done')
        self.assertEqual(levels, ['lossless', 'exhigh', 'standard'])
        self.assertEqual(self.manager.jobs[-1].level, 'standard')

    def test_quota_exhaustion_stops_waiting_letters_for_every_platform(self):
        self.resolve.side_effect = dl.ApiError('额度已用尽', 402)
        notices = self.bus.subscribe()
        self.manager.max_workers = 1
        self.manager.enqueue([song(1), song(2, 'qq'), song(3, 'kugou')], self.settings, 'chksz_a')
        kinds = []
        wait_until(lambda: kinds.append(notices.get(timeout=5)['type']) or 'notice' in kinds)
        self.assertEqual(self.states(), ['failed', 'failed', 'failed'])
        self.assertEqual(self.resolve.call_count, 1)
        self.assertTrue(all('暂缓' in job.detail for job in self.manager.jobs[1:]))

    def test_outage_only_stops_the_same_platform(self):
        def outage(key, sid, level):
            if sid == '1':
                raise dl.ApiError('熔断', 503)
            return {'url': 'https://cdn.test/x.flac', 'level': level}

        self.resolve.side_effect = outage
        self.gate.set()
        self.manager.max_workers = 1
        self.manager.enqueue([song(1, 'kugou'), song(2, 'kugou'), song(3, 'netease')], self.settings, 'chksz_a')
        wait_until(lambda: not self.manager.active())
        self.assertEqual(self.states(), ['failed', 'failed', 'done'])

    def test_retry_uses_new_key_and_original_settings(self):
        self.resolve.side_effect = dl.ApiError('invalid key', 401)
        self.manager.enqueue([song(1)], self.settings, 'chksz_old')
        wait_until(lambda: self.states() == ['failed'])
        self.resolve.side_effect = lambda key, sid, level: {'url': 'https://cdn.test/1.flac', 'level': level}
        self.gate.set()
        self.assertEqual(self.manager.retry('chksz_new'), 1)
        wait_until(lambda: self.states() == ['done'] and len(self.history.records) == 1)
        self.assertEqual(self.resolve.call_args.args[0], 'chksz_new')
        self.assertEqual(self.resolve.call_args.args[2], 'lossless')
        self.assertEqual(self.history.records[0]['state'], 'done')

    def test_previous_session_letter_can_be_resent(self):
        self.gate.set()
        record_settings = Settings(out_dir=str(self.root / 'old'), qualities={'netease': 'exhigh', 'qq': 'flac', 'kugou': 'flac'})
        self.history.add({'id': 'old1', 'song': song(9), 'state': 'failed', 'detail': 'x', 'finished': 1,
                          'settings': core.asdict(record_settings)})
        fresh = DownloadManager(self.bus, History(self.root / 'history.json'))
        self.addCleanup(lambda: wait_until(lambda: fresh.running == 0))
        self.addCleanup(fresh.shutdown)
        self.assertEqual(fresh.retry_record('old1', 'chksz_new'), 1)
        wait_until(lambda: fresh.jobs and fresh.jobs[0].state == 'done' and fresh.history.records)
        self.assertTrue((self.root / 'old' / '歌手 - 歌9.flac').is_file())
        self.assertEqual(self.resolve.call_args.args[2], 'exhigh')
        self.assertIsNone(fresh.history.get('old1'))

    def test_history_persists_without_keys(self):
        self.gate.set()
        self.manager.enqueue([song(1)], self.settings, 'chksz_secret_value')
        wait_until(lambda: self.history.records)
        text = (self.root / 'history.json').read_text(encoding='utf-8')
        self.assertNotIn('chksz_', text)
        self.assertEqual(History(self.root / 'history.json').records[0]['song']['name'], '歌1')

    def test_requires_key(self):
        with self.assertRaises(PermissionError):
            self.manager.enqueue([song(1)], self.settings, None)


class SettingsAndKeyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def test_new_settings_are_cleaned(self):
        s = core.Settings.from_dict({
            'stationery': {'paper': 'kraft', 'seal_motif': 'quill', 'ink': '<b>', 'evil': 1, 'signoff': 'x' * 40},
            'photo_stamps': ['0123456789abcdef.jpg', '../secret.txt', '0123456789abcdef.jpg'],
            'letter_charts': ['qq:62', 'netease:3779629', 'kugou:1', 'qq:62'], 'letter_count': 9, 'letter_taste': False,
            'nickname': '  小   满  ', 'lyrics_size': 99, 'lyrics_pos': [10, 20], 'desktop_lyrics': True,
        })
        self.assertEqual((s.stationery['paper'], s.stationery['seal_motif'], s.stationery['ink']), ('kraft', 'quill', 'violet'))
        self.assertNotIn('evil', s.stationery)
        self.assertEqual(len(s.stationery['signoff']), 16)
        self.assertEqual(s.photo_stamps, ['0123456789abcdef.jpg'])
        self.assertEqual(s.letter_charts, ['qq:62', 'netease:3779629'])
        self.assertEqual((s.letter_count, s.letter_taste, s.nickname), (3, False, '小 满'))
        self.assertEqual((s.lyrics_size, s.lyrics_pos, s.desktop_lyrics), (32, [10, 20], True))
        with self.assertRaises(ValueError):
            core.Settings.from_dict({'letter_playlists': ['https://example.com/list']})

    def test_settings_validate_and_never_store_key(self):
        path = self.root / 'prefs.json'
        with patch('violet_core.SETTINGS_FILE', path):
            Settings.from_dict({'theme': 'violet', 'qualities': {'netease': 'bogus', 'qq': '320k'},
                                'out_dir': '  ', 'sound': 'yes', 'library_dirs': ['D:/a', 3, '']}).save()
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertNotIn('key', ' '.join(data).lower())
            loaded = Settings.load()
        self.assertEqual(loaded.theme, 'auto')
        self.assertEqual(loaded.qualities, {'netease': 'lossless', 'qq': '320k', 'kugou': 'flac'})
        self.assertEqual(loaded.out_dir, './music')
        self.assertFalse(loaded.sound)
        self.assertEqual(loaded.library_dirs, ['D:/a'])

    def test_relative_folders_anchor_to_app_directory(self):
        self.assertEqual(core.resolve_dir('./music'), os.path.normpath(os.path.join(core.APP_DIR, 'music')))

    def test_installed_copy_keeps_songs_in_music_folder(self):
        home = os.path.join(os.path.expanduser('~'), 'Music', 'Violet')
        with patch('violet_core.installed', return_value=True):
            self.assertEqual(core.resolve_dir('./music'), os.path.normpath(home))
            self.assertEqual(core.resolve_dir('more'), os.path.normpath(os.path.join(home, 'more')))
            self.assertEqual(core.resolve_dir('D:/songs'), os.path.normpath('D:/songs'))

    def test_key_store_remember_and_forget(self):
        key_file = self.root / '.chksz_key'
        with patch.dict(os.environ, {'CHKSZ_API_KEY': ''}), patch('violet_core.APP_DIR', self.root):
            store = KeyStore(key_file)
            self.assertFalse(store.status()['has_key'])
            with self.assertRaises(ValueError):
                store.set('not-a-key', True)
            store.set('chksz_abcdEFGH1234', remember=False)
            self.assertFalse(key_file.exists())
            self.assertEqual(store.status()['masked'], 'chksz_…1234')
            store.set('chksz_abcdEFGH1234', remember=True)
            self.assertEqual(KeyStore(key_file).key, 'chksz_abcdEFGH1234')
            store.forget()
            self.assertFalse(key_file.exists())
            self.assertIsNone(store.key)

    def test_environment_key_wins(self):
        key_file = self.root / '.chksz_key'
        key_file.write_text('chksz_fromfile\n', encoding='utf-8')
        with patch.dict(os.environ, {'CHKSZ_API_KEY': 'chksz_fromenv'}):
            store = KeyStore(key_file)
        self.assertEqual((store.key, store.source), ('chksz_fromenv', 'env'))


if __name__ == '__main__':
    unittest.main()


class MigrationTests(unittest.TestCase):
    def test_old_data_is_copied_once_and_relative_folders_are_pinned(self):
        with tempfile.TemporaryDirectory() as old, tempfile.TemporaryDirectory() as new:
            old, new = Path(old), Path(new) / 'Violet'
            (old / '.violet_settings.json').write_text(json.dumps({'out_dir': './music', 'library_dirs': ['../more']}),
                                                       encoding='utf-8')
            (old / '.violet_letters.json').write_text('[]', encoding='utf-8')
            self.assertEqual(core.migrate_legacy(new, [old]), old)
            settings = json.loads((new / 'settings.json').read_text(encoding='utf-8'))
            self.assertEqual(settings['out_dir'], os.path.normpath(str(old / 'music')))
            self.assertEqual(settings['library_dirs'], [os.path.normpath(str(old.parent / 'more'))])
            self.assertTrue((new / 'letters.json').is_file())
            self.assertTrue((old / '.violet_settings.json').is_file(), 'originals stay where they were')
            self.assertIsNone(core.migrate_legacy(new, [old]))

    def test_v4_line_drawing_setting_becomes_the_watercolour(self):
        self.assertEqual(Settings.from_dict({'portrait': 'ink'}).portrait, 'art')
        self.assertEqual(Settings.from_dict({'tray': False, 'intro': False}).tray, False)
