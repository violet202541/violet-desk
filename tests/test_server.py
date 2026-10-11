from datetime import datetime
import http.client
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import chksz_dl as dl
import violet_server
from violet_core import History, KeyStore, Settings
from violet_desk import Desk
from violet_letters import Letters, Plays
from violet_library import Library, read_lyrics, read_tags
from violet_server import VioletServer, VioletService


def write_wav(path, seconds=1, rate=8000):
    frames = b'\x00\x00' * rate * seconds
    header = b'RIFF' + struct.pack('<I', 36 + len(frames)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate * 2, 2, 16)
    Path(path).write_bytes(header + b'data' + struct.pack('<I', len(frames)) + frames)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        web = self.root / 'web'
        web.mkdir()
        (web / 'index.html').write_text('<title>Violet</title>', encoding='utf-8')
        (self.root / 'secret.txt').write_text('secret', encoding='utf-8')
        patches = [patch.object(violet_server, 'WEB_DIR', web), patch('violet_core.SETTINGS_FILE', self.root / 'prefs.json'),
                   patch.dict(os.environ, {'CHKSZ_API_KEY': ''})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.music = self.root / 'music'
        self.music.mkdir()
        library, plays = Library(self.root / 'lib.json'), Plays(self.root / 'plays.json')
        self.desk = Desk(self.root / 'desk.db')
        self.addCleanup(self.desk.close)
        self.service = VioletService(settings=Settings(out_dir=str(self.music)), keys=KeyStore(self.root / 'key'),
                                     history=History(self.root / 'history.json'), library=library, plays=plays,
                                     letters=Letters(library, plays, self.root / 'letters.json'), desk=self.desk,
                                     data_dir=self.root)
        self.server = VioletServer(self.service)
        self.server.start()
        self.addCleanup(self.server.stop)
        self.port = self.server.server_address[1]

    def request(self, method, path, body=None, token=True, headers=None, raw=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        all_headers = dict(headers or {})
        if token:
            all_headers['X-Violet-Token'] = self.service.token
        payload = json.dumps(body).encode() if body is not None else raw
        if payload and 'Content-Type' not in all_headers:
            all_headers['Content-Type'] = 'application/json'
        conn.request(method, path, body=payload, headers=all_headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, dict(response.getheaders()), data

    def json(self, method, path, body=None, **kw):
        status, _, data = self.request(method, path, body, **kw)
        return status, json.loads(data.decode('utf-8'))

    def test_api_requires_session_token(self):
        self.assertEqual(self.request('GET', '/api/state', token=False)[0], 403)
        self.assertEqual(self.request('POST', '/api/settings', {}, token=False)[0], 403)
        status, state = self.json('GET', '/api/state')
        self.assertEqual(status, 200)
        self.assertFalse(state['key']['has_key'])
        self.assertEqual(self.request('GET', f'/api/state?t={self.service.token}', token=False)[0], 200)

    def test_static_files_never_escape_web_root(self):
        status, _, body = self.request('GET', '/', token=False)
        self.assertEqual((status, body), (200, b'<title>Violet</title>'))
        for path in ('/../secret.txt', '/%2e%2e/secret.txt', '/..%5csecret.txt'):
            status, _, body = self.request('GET', path, token=False)
            self.assertNotIn(b'secret', body)

    def test_image_proxy_only_allows_music_cdns(self):
        for url in ('http://127.0.0.1:1/x.jpg', 'file:///C:/Windows/win.ini', 'https://evil.example/x.jpg',
                    'https://126.net.evil.example/x.jpg'):
            status, body = self.json('GET', '/api/img?u=' + url)
            self.assertEqual(status, 401, url)

    def test_search_without_key_and_upstream_errors(self):
        status, body = self.json('GET', '/api/search?q=a&platform=netease')
        self.assertEqual((status, body['code']), (401, 'no_key'))
        self.service.keys.set('chksz_test1234', remember=False)
        with patch.dict(dl.SEARCH, {'kugou': lambda *a, **k: (_ for _ in ()).throw(dl.ApiError('平台暂不可用（503）', 503))}):
            status, body = self.json('GET', '/api/search?q=a&platform=kugou')
        self.assertEqual(status, 502)
        self.assertIn('503', body['error'])
        with patch.dict(dl.SEARCH, {'netease': lambda key, q, **k: [{'id': '1', 'name': q}]}):
            status, body = self.json('GET', '/api/search?q=%E6%99%B4&platform=netease')
        self.assertEqual(body['songs'], [{'id': '1', 'name': '晴', 'platform': 'netease'}])

    def test_settings_roundtrip_and_key_not_persisted_in_settings(self):
        status, body = self.json('POST', '/api/settings', {'theme': 'dark', 'sound': True, 'qualities': {'qq': '128k'}})
        self.assertEqual(status, 200)
        self.assertEqual((body['theme'], body['sound'], body['qualities']['qq']), ('dark', True, '128k'))
        status, key = self.json('POST', '/api/key', {'key': 'chksz_abc123', 'remember': False})
        self.assertTrue(key['has_key'])
        self.assertNotIn('chksz', (self.root / 'prefs.json').read_text(encoding='utf-8'))
        status, body = self.json('POST', '/api/key', {'key': 'bad key', 'remember': False})
        self.assertEqual(status, 400)

    def test_downloads_require_key_then_enqueue(self):
        status, body = self.json('POST', '/api/downloads', {'songs': [{'platform': 'netease', 'id': '1'}]})
        self.assertEqual((status, body['code']), (401, 'no_key'))
        self.service.keys.set('chksz_abc123', remember=False)
        with patch.object(self.service.downloads, 'enqueue', return_value=([object()], 1)) as enqueue:
            status, body = self.json('POST', '/api/downloads', {'songs': [{'platform': 'netease', 'id': '1'}]})
        self.assertEqual(body, {'added': 1, 'duplicates': 1})
        self.assertEqual(enqueue.call_args.args[2], 'chksz_abc123')

    def test_library_audio_supports_ranges_and_unknown_ids_404(self):
        write_wav(self.music / '歌手 - 歌名.wav')
        (self.music / '歌手 - 歌名.lrc').write_bytes('[00:01.00]第一句'.encode('gb18030'))
        status, body = self.json('GET', '/api/library?refresh=1')
        track = body['tracks'][0]
        self.assertEqual((track['title'], track['artist'], track['has_lyrics']), ('歌名', '歌手', True))
        status, headers, data = self.request('GET', f'/api/library/{track["id"]}/audio', headers={'Range': 'bytes=0-3'})
        self.assertEqual((status, data), (206, b'RIFF'))
        self.assertEqual(headers['Content-Range'], f'bytes 0-3/{track["size"]}')
        status, body = self.json('GET', f'/api/library/{track["id"]}/lyrics')
        self.assertEqual(body['lyrics'], '[00:01.00]第一句')
        self.assertEqual(self.request('GET', '/api/library/deadbeefdeadbeef/audio')[0], 404)
        self.assertEqual(self.request('GET', '/api/library/../../secret/audio')[0], 404)

    def test_keep_alive_post_body_never_leaks_into_next_request(self):
        write_wav(self.music / 'a - b.wav')
        self.json('GET', '/api/library?refresh=1')
        track = self.service.library.list()[0]['id']
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        headers = {'X-Violet-Token': self.service.token, 'Content-Type': 'application/json'}
        conn.request('POST', f'/api/library/{track}/played', body=b'{}', headers=headers)
        self.assertEqual(conn.getresponse().read() and 200, 200)
        conn.request('GET', '/api/letters', headers=headers)
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        response.read()
        conn.close()

    def test_paged_search_per_platform(self):
        self.service.keys.set('chksz_test1234', remember=False)
        calls = []

        def netease(key, q, limit=20, offset=0):
            calls.append(('netease', limit, offset))
            return [{'id': str(offset + i), 'name': q} for i in range(limit)]

        def qq(key, q, num=10):
            calls.append(('qq', num))
            return [{'id': f'q{i}', 'name': q} for i in range(num)]

        with patch.dict(dl.SEARCH, {'netease': netease, 'qq': qq, 'kugou': lambda key, q: [{'id': 'k'}]}):
            _, page1 = self.json('GET', '/api/search?q=a&platform=netease&page=1')
            _, qq0 = self.json('GET', '/api/search?q=a&platform=qq')
            _, qq1 = self.json('GET', '/api/search?q=a&platform=qq&page=1')
            _, kg1 = self.json('GET', '/api/search?q=a&platform=kugou&page=1')
        self.assertEqual((page1['songs'][0]['id'], page1['has_more']), ('20', True))
        self.assertEqual((len(qq0['songs']), qq0['has_more'], len(qq1['songs']), qq1['has_more']), (20, True, 50, False))
        self.assertEqual((kg1['songs'], kg1['has_more']), ([], False))
        self.assertIn(('netease', 20, 20), calls)

    def test_portrait_only_serves_the_configured_image(self):
        self.assertEqual(self.request('GET', '/api/portrait')[0], 400)
        image = self.root / 'violet.png'
        image.write_bytes(b'PNGDATA')
        status, body = self.json('POST', '/api/settings', {'portrait': 'custom', 'portrait_path': str(image)})
        self.assertEqual(body['portrait'], 'custom')
        status, headers, data = self.request('GET', '/api/portrait')
        self.assertEqual((status, data), (200, b'PNGDATA'))
        status, body = self.json('POST', '/api/settings', {'portrait_path': str(self.root / 'secret.txt')})
        self.assertEqual(body['portrait_path'], str(image))

    def test_events_stream_delivers_published_messages(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        conn.request('GET', f'/api/events?t={self.service.token}')
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.readline(), b'retry: 1500\n')
        response.readline()
        self.service.bus.publish('quota', {'free': 7})
        line = response.readline().decode('utf-8')
        self.assertEqual(json.loads(line[len('data: '):]), {'type': 'quota', 'data': {'free': 7}})
        conn.close()


    def test_sending_songs_back_moves_files_to_the_bin_and_lets_go_of_them(self):
        binned = []
        self.service.recycle = lambda paths: [binned.append(Path(x).name) or Path(x).unlink() for x in paths]
        for folder in ('one', 'two'):
            (self.music / folder).mkdir()
            write_wav(self.music / folder / 'Violet - Sincerely.wav', seconds=2 if folder == 'one' else 1)
        (self.music / 'one' / 'Violet - Sincerely.lrc').write_text('[00:00.00]x', encoding='utf-8')
        write_wav(self.music / 'Violet - Alone.wav')
        tracks = {t['path']: t['id'] for t in self.service.library.scan([str(self.music)])}
        first = tracks[str(self.music / 'one' / 'Violet - Sincerely.wav')]
        second = tracks[str(self.music / 'two' / 'Violet - Sincerely.wav')]
        alone = tracks[str(self.music / 'Violet - Alone.wav')]
        library = self.service.library.tracks
        self.service.shelf.press(library[first])
        self.service.shelf.press(library[alone])
        bundle = self.service.shelf.create_bundle({'name': '雨天'})
        self.service.shelf.add(bundle['id'], [library[first], library[alone]])
        self.desk.create_reply({'body': '你好', 'song': {'id': alone, 'title': 'Alone'}})
        self.service.history.add({'id': 'r1', 'path': str(self.music / 'Violet - Alone.wav')})

        status, data = self.json('GET', '/api/library/duplicates')
        self.assertEqual(status, 200)
        self.assertEqual(len(data['groups']), 1)
        self.assertEqual(data['groups'][0]['copies'][0]['id'], first)  # the longer copy has more to it

        status, data = self.json('POST', '/api/library/references', {'ids': [alone, first]})
        refs = {r['id']: r for r in data['items']}
        self.assertEqual(refs[alone]['bundles'], ['雨天'])
        self.assertTrue(refs[alone]['pressed'])
        self.assertEqual(refs[alone]['replies'], 1)
        self.assertFalse(refs[alone]['twin'])
        self.assertTrue(refs[first]['twin'])

        status, data = self.json('POST', '/api/library/delete', {'ids': [first, alone, 'nope']})
        self.assertEqual(status, 200)
        self.assertEqual(sorted(data['removed']), sorted([first, alone]))
        self.assertEqual([f['id'] for f in data['failed']], ['nope'])
        self.assertIn('Violet - Sincerely.lrc', binned)
        self.assertFalse((self.music / 'Violet - Alone.wav').exists())
        self.assertNotIn(first, self.service.library.tracks)
        # The flower and the bundle letter follow the copy that is left; the lone song is taken down.
        self.assertEqual(self.service.shelf.pressed_ids(), [second])
        letters = self.service.shelf.bundle(bundle['id'], self.service.library.tracks)['letters']
        self.assertEqual([l['track_id'] for l in letters], [second])
        self.assertIsNone(self.service.history.get('r1'))
        # The reply keeps the song's name.
        self.assertEqual(self.desk.replies()[0]['song']['title'], 'Alone')

    def test_a_song_that_cannot_be_binned_stays(self):
        def refuse(paths):
            raise OSError('文件正被占用')
        self.service.recycle = refuse
        write_wav(self.music / 'Violet - Alone.wav')
        tid = self.service.library.scan([str(self.music)])[0]['id']
        status, data = self.json('POST', '/api/library/delete', {'ids': [tid]})
        self.assertEqual((data['removed'], data['failed'][0]['error']), ([], '文件正被占用'))
        self.assertIn(tid, self.service.library.tracks)


class DeskApiTests(unittest.TestCase):
    setUp, request, json = ServerTests.setUp, ServerTests.request, ServerTests.json

    def test_commission_conflict_returns_409_with_current(self):
        status, item = self.json('POST', '/api/commissions', {'title': '写周报', 'due_date': '2026-10-10'})
        self.assertEqual(status, 200)
        status, updated = self.json('POST', f'/api/commissions/{item["id"]}', {'title': '写周报（终）', 'revision': 1})
        self.assertEqual((status, updated['revision']), (200, 2))
        status, body = self.json('POST', f'/api/commissions/{item["id"]}', {'title': '旧的', 'revision': 1})
        self.assertEqual((status, body['code'], body['current']['title']), (409, 'conflict', '写周报（终）'))
        status, body = self.json('POST', f'/api/commissions/{item["id"]}/complete', {'done': True})
        self.assertEqual(body['commission']['status'], 'done')
        status, listing = self.json('GET', '/api/commissions')
        self.assertEqual(len(listing['commissions']), 1)

    def test_reply_seal_and_calendar(self):
        status, reply = self.json('POST', '/api/replies', {'body': '亲爱的 Violet：', 'mood': 'warm'})
        self.assertEqual(status, 200)
        status, sealed = self.json('POST', f'/api/replies/{reply["id"]}/seal', {'recipient': 'violet'})
        self.assertEqual(sealed['state'], 'sealed')
        status, body = self.json('POST', f'/api/replies/{reply["id"]}', {'body': '改'})
        self.assertEqual(status, 400)
        status, month = self.json('GET', '/api/calendar?month=' + reply['date'][:7])
        self.assertEqual(len(month['days']), 42)
        day = next(d for d in month['days'] if d['date'] == reply['date'])
        self.assertEqual(day['reply']['mood'], 'warm')
        self.assertEqual(self.json('GET', '/api/calendar?month=2026-13')[0], 400)

    def test_shelf_presses_and_bundles_songs(self):
        song = {'id': 't1', 'title': 'Sincerely', 'artist': 'TRUE', 'album': '', 'has_cover': False, 'duration': 1000,
                'mtime': 0, 'path': str(self.music / 'x.flac')}
        self.service.library.tracks = {'t1': song}
        status, body = self.json('POST', '/api/pressed', {'track_id': 't1', 'note': '雨天'})
        self.assertEqual((status, body['ids']), (200, ['t1']))
        self.assertEqual(self.json('POST', '/api/pressed', {'track_id': 'nope'})[0], 400)
        status, bundle = self.json('POST', '/api/bundles', {'name': '雨天读的信', 'ribbon': 'wine', 'track_ids': ['t1'],
                                                            'songs': [{'name': '晴天', 'artist': '周杰伦'}]})
        self.assertEqual((status, bundle['here'], bundle['pending']), (200, 1, 1))
        status, added = self.json('POST', f'/api/bundles/{bundle["id"]}/add', {'track_ids': ['t1']})
        self.assertEqual((added['added'], added['duplicates']), (0, 1))
        status, shelf = self.json('GET', '/api/shelf')
        self.assertEqual((shelf['bundles'][0]['name'], shelf['pressed'][0]['note']), ('雨天读的信', '雨天'))
        self.assertEqual(shelf['memberships'], {'t1': [bundle['id']]})
        today = self.service.desk.today().isoformat()
        status, month = self.json('GET', '/api/calendar?month=' + today[:7])
        self.assertEqual(next(d for d in month['days'] if d['date'] == today)['pressed'], 1)
        self.assertEqual(self.json('GET', '/api/day?date=' + today)[1]['pressed'][0]['title'], 'Sincerely')
        self.assertEqual(self.json('POST', f'/api/bundles/{bundle["id"]}/delete', {})[0], 200)
        self.assertEqual(self.json('GET', f'/api/bundles/{bundle["id"]}')[0], 400)

    def test_geese_card_fetch_cabinet_and_letter(self):
        from tests.test_geese import DETAIL_HTML, LIST_HTML, PACK, FakeCourier
        pack = {**PACK, 'id': 'testu', 'routes': PACK['routes'][:2]}
        pages = {'https://jw.example.edu/jxxx/tzgg.htm': LIST_HTML,
                 'https://jw.example.edu/info/1164/29998.htm': DETAIL_HTML}
        self.service.geese.courier = FakeCourier(pages)
        status, preview = self.json('POST', '/api/geese/packs/preview', {'pack': json.dumps(pack)})
        self.assertEqual((status, preview['pack']['id'], len(preview['sample'])), (200, 'testu', 5))
        self.assertEqual(self.json('POST', '/api/geese/packs/preview', {'pack': '{"id": 1}'})[1]['code'], 'route')
        self.assertEqual(self.json('POST', '/api/geese/packs/install', {'pack': pack})[0], 200)
        card = {'school': 'testu', 'entry_year': 2024, 'cares': [{'id': 'contest', 'name': '竞赛', 'keywords': ['竞赛']}]}
        status, trial = self.json('POST', '/api/geese/trial', card)
        self.assertEqual((status, trial['kept_count']), (200, 1))
        self.assertEqual(self.json('POST', '/api/geese/card', card)[0], 200)
        status, cabinet = self.json('GET', '/api/geese')
        letter = next(l for l in cabinet['letters'] if l['cubby'] == 'contest')
        self.assertEqual(letter['deadline'], '2026-10-11')
        self.assertNotIn('content', letter)
        status, full = self.json('GET', f'/api/geese/letters/{letter["id"]}')
        self.assertIn('2026年10月11日', full['content'])
        self.assertTrue(full['read_at'])
        status, pinned = self.json('POST', f'/api/geese/letters/{letter["id"]}', {'pinned': True})
        self.assertEqual(pinned['pinned'], 1)
        status, drawer = self.json('GET', '/api/geese/drawer?box=unopened')
        self.assertEqual(len(drawer['letters']), 4)
        status, words = self.json('GET', f'/api/geese/letters/{drawer["letters"][0]["id"]}/words')
        self.assertEqual(status, 200)
        self.assertEqual(self.json('POST', '/api/geese/portals/ecampus/login', {})[0], 400)  # no window in tests

    def test_photo_upload_checks_the_bytes(self):
        png = b'\x89PNG\r\n\x1a\n' + b'0' * 64
        status, _, data = self.request('POST', '/api/photos', headers={'Content-Type': 'image/png'}, raw=png)
        name = json.loads(data)['name']
        self.assertEqual(status, 200)
        status, _, body = self.request('GET', f'/api/photos/{name}')
        self.assertEqual((status, body), (200, png))
        self.assertEqual(self.request('POST', '/api/photos', raw=b'<script>')[0], 400)
        self.assertEqual(self.request('GET', '/api/photos/..%2Fsecret.txt')[0], 400)

    def test_backup_and_restore_round_trip(self):
        self.json('POST', '/api/commissions', {'title': '备份之前'})
        status, result = self.json('POST', '/api/backups/run', {})
        self.assertEqual(status, 200)
        name = Path(result['local']).name
        self.json('POST', '/api/commissions', {'title': '备份之后'})
        status, _ = self.json('POST', '/api/backups/restore', {'name': name, 'where': 'local'})
        self.assertEqual(status, 200)
        titles = [c['title'] for c in self.json('GET', '/api/commissions')[1]['commissions']]
        self.assertEqual(titles, ['备份之前'])
        status, listing = self.json('GET', '/api/backups')
        self.assertGreaterEqual(len(listing['local']), 2)  # the restore made a safety copy first
        self.assertEqual(self.json('POST', '/api/backups/restore', {'name': '../x.zip', 'where': 'local'})[0], 400)

    def test_reminders_publish_and_notify(self):
        notes = []
        self.service.hooks['notify'] = lambda title, text: notes.append((title, text))
        self.json('POST', '/api/commissions', {'title': '喝水', 'due_date': '2026-10-10', 'due_time': '09:00',
                                               'remind': 0})
        fired = self.service.check_reminders(now=datetime(2026, 10, 10, 9, 1).timestamp())
        self.assertEqual(len(fired), 1)
        self.assertIn('喝水', notes[0][1])

    def test_image_redirects_must_stay_on_music_hosts(self):
        self.assertTrue(violet_server.image_host_allowed('https://p1.music.126.net/a.jpg'))
        self.assertFalse(violet_server.image_host_allowed('https://p1.music.126.net:8443/a.jpg'))
        self.assertFalse(violet_server.image_host_allowed('http://127.0.0.1/a.jpg'))
        handler = violet_server._CheckedRedirect()
        with self.assertRaises(PermissionError):
            handler.redirect_request(None, None, 302, 'Found', {}, 'http://169.254.169.254/latest')


class LibraryTests(unittest.TestCase):
    def test_tags_fall_back_to_filename_and_cache_is_used(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Artist - Title.wav'
            write_wav(path)
            info = read_tags(str(path))
            self.assertEqual((info['title'], info['artist']), ('Title', 'Artist'))
            self.assertGreater(info['duration'], 900)
            library = Library(Path(folder) / 'cache.json')
            self.assertEqual(len(library.scan([folder])), 1)
            with patch('violet_library.read_tags', side_effect=AssertionError('cache miss')):
                self.assertEqual(len(Library(Path(folder) / 'cache.json').scan([folder])), 1)

    def test_sidecar_lyrics_accept_utf8_bom_and_gb18030(self):
        with tempfile.TemporaryDirectory() as folder:
            audio = Path(folder) / 'a.wav'
            write_wav(audio)
            for raw in ('\ufeff[00:00.00]你好'.encode('utf-8'), '[00:00.00]你好'.encode('gb18030')):
                (Path(folder) / 'a.lrc').write_bytes(raw)
                self.assertEqual(read_lyrics(str(audio)), '[00:00.00]你好')


if __name__ == '__main__':
    unittest.main()
