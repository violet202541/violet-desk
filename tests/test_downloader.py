import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import chksz_dl as dl


class Response(io.BytesIO):
    def __init__(self, body, length=None, content_type='audio/mpeg'):
        super().__init__(body)
        self.headers = {'Content-Length': str(len(body) if length is None else length),
                        'Content-Type': content_type}


class StreamTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'song.mp3'

    def assert_clean(self):
        self.assertFalse(self.path.exists())
        self.assertEqual(list(Path(self.folder.name).glob('*.part')), [])

    def test_complete_audio_is_published(self):
        with patch.object(dl.urllib.request, 'urlopen', return_value=Response(b'audio')):
            self.assertEqual(dl.stream_download('https://example.test/song', self.path), 5)
        self.assertEqual(self.path.read_bytes(), b'audio')
        self.assertEqual(list(Path(self.folder.name).glob('*.part')), [])

    def test_truncated_audio_is_not_published(self):
        with patch.object(dl.urllib.request, 'urlopen', return_value=Response(b'audio', length=100)):
            with self.assertRaises(RuntimeError):
                dl.stream_download('https://example.test/song', self.path)
        self.assert_clean()

    def test_empty_or_error_page_is_not_published(self):
        for body, content_type in ((b'', 'audio/mpeg'), (b'<html>error</html>', 'text/html')):
            with patch.object(dl.urllib.request, 'urlopen', return_value=Response(body, content_type=content_type)):
                with self.assertRaises(RuntimeError):
                    dl.stream_download('https://example.test/song', self.path)
            self.assert_clean()

    def test_mid_download_cancel_cleans_partial(self):
        cancel = threading.Event()
        with patch.object(dl.urllib.request, 'urlopen', return_value=Response(b'audio')):
            with self.assertRaises(dl.DownloadCancelled):
                dl.stream_download('https://example.test/song', self.path,
                                   progress=lambda *_: cancel.set(), cancel=cancel)
        self.assert_clean()

    def test_concurrent_target_is_never_overwritten(self):
        with patch.object(dl.urllib.request, 'urlopen', return_value=Response(b'audio')):
            with self.assertRaises(FileExistsError):
                dl.stream_download('https://example.test/song', self.path,
                                   progress=lambda *_: self.path.write_bytes(b'existing'))
        self.assertEqual(self.path.read_bytes(), b'existing')
        self.assertEqual(list(Path(self.folder.name).glob('*.part')), [])

    def test_existing_target_does_not_make_request(self):
        self.path.write_bytes(b'existing')
        with patch.object(dl.urllib.request, 'urlopen') as request:
            with self.assertRaises(FileExistsError):
                dl.stream_download('https://example.test/song', self.path)
        request.assert_not_called()


class ApiTests(unittest.TestCase):
    def test_kugou_duration_is_seconds(self):
        with patch.object(dl, 'api', return_value=({'code': 200, 'msg': 'success',
                                                  'list': [{'id': 'kg', 'duration': 176}]}, {})):
            self.assertEqual(dl.search_kugou('test', 'song')[0]['duration'], 176000)

    def test_netease_accepts_both_documented_and_live_shape(self):
        song = {'id': 1, 'name': 'test'}
        for data in ([song], {'songs': [song]}):
            with patch.object(dl, 'api', return_value=({'code': 200, 'msg': 'success', 'data': data}, {})):
                self.assertEqual(dl.search_netease('test', 'song')[0]['id'], '1')

    def test_aggregate_preserves_partial_results_and_reports_errors(self):
        failures = []
        def broken(*_):
            raise dl.ApiError('unavailable', 503)
        with patch.dict(dl.SEARCH, {'netease': lambda *_: [{'id': '1'}], 'qq': broken, 'kugou': broken}):
            result = dl.search_all('test', 'song', on_error=failures.append)
        self.assertEqual(result, [{'id': '1', 'platform': 'netease'}])
        self.assertEqual(len(failures), 2)

    def test_windows_names_stay_inside_output_directory(self):
        for name in ('..', '.', 'CON', 'NUL.txt', 'LPT1', 'a/b', 'trailing. ', '\x00'):
            sanitized = dl.sanitize(name)
            self.assertNotIn(sanitized, ('.', '..', ''))
            self.assertNotIn('/', sanitized)
            self.assertNotIn('\\', sanitized)
        self.assertEqual(dl.sanitize('CON'), '_CON')

    def test_playlist_parser_does_not_select_arbitrary_tracking_number(self):
        self.assertEqual(dl.parse_playlist_id('https://y.qq.com/n/ryqq/playlist/9080103532'), '9080103532')
        self.assertEqual(dl.parse_playlist_id('https://music.163.com/#/playlist?id=12345'), '12345')
        with self.assertRaises(RuntimeError):
            dl.parse_playlist_id('https://example.test/?tracking=123456789')

    def test_search_404_means_no_results_but_outage_raises(self):
        for search in (dl.search_qq, dl.search_kugou):
            with patch.object(dl, 'api', side_effect=dl.ApiError('未找到匹配的歌曲', 404)):
                self.assertEqual(search('test', 'song'), [])
            with patch.object(dl, 'api', side_effect=dl.ApiError('熔断', 503)):
                with self.assertRaises(dl.ApiError):
                    search('test', 'song')

    def test_http_error_message_uses_upstream_msg_and_hides_key(self):
        body = io.BytesIO('{"code": 503, "msg": "上游连续失败 chksz_secret"}'.encode('utf-8'))
        error = dl.urllib.error.HTTPError('https://example.test', 503, 'x', {}, body)
        with patch.object(dl.urllib.request, 'urlopen', side_effect=error):
            with self.assertRaises(dl.ApiError) as caught:
                dl.api('/api/qq_music', {}, 'chksz_secret')
        self.assertEqual(caught.exception.status, 503)
        self.assertIn('上游连续失败', str(caught.exception))
        self.assertNotIn('chksz_secret', str(caught.exception))
        self.assertNotIn('{', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
