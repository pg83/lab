#!/usr/bin/env python3

import importlib.util
import io
import sys
import types
import unittest
import unittest.mock
from pathlib import Path


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# http.py imports the upstream config for the user agent.
sys.modules.setdefault('repology', types.ModuleType('repology'))
sys.modules['repology.config'] = types.SimpleNamespace(config={'REPOLOGY_HOME': 'https://repology.example'})

jsonslicer = load('jsonslicer', 'jsonslicer.py')
http = load('http', 'http.py')
repology = load('repology_job', 'repology.py')


class JsonSlicerShim(unittest.TestCase):
    DOC = b'{"packages": {"a": {"v": 1}, "b": {"v": 2}}, "ports": [{"n": "x"}, {"n": "y"}]}'

    def test_list_items(self):
        items = list(jsonslicer.JsonSlicer(io.BytesIO(self.DOC), ('ports', None)))
        self.assertEqual(items, [{'n': 'x'}, {'n': 'y'}])

    def test_map_keys(self):
        items = list(jsonslicer.JsonSlicer(io.BytesIO(self.DOC), ('packages', None), path_mode='map_keys', encoding='utf-8'))
        self.assertEqual(items, [('a', {'v': 1}), ('b', {'v': 2})])

    def test_full_path(self):
        items = list(jsonslicer.JsonSlicer(io.BytesIO(self.DOC), ('packages', None, None), path_mode='full'))
        self.assertEqual(items, [('packages', 'a', 'v', 1), ('packages', 'b', 'v', 2)])

    def test_top_level_list(self):
        items = list(jsonslicer.JsonSlicer(io.BytesIO(b'[1, 2]'), (None,)))
        self.assertEqual(items, [1, 2])

    def test_whitespace_nesting_and_skipped_siblings(self):
        doc = b'''
        {
          "meta": {"x": [1, 2, {"y": "z"}], "n": null},
          "packages": {
            "a": {"v": 1, "deep": [ {"k": "}" } ]},
            "b": {"v": "]"}
          },
          "tail": [true, false]
        }
        '''
        items = list(jsonslicer.JsonSlicer(io.BytesIO(doc), ('packages', None), path_mode='map_keys'))
        self.assertEqual(items, [('a', {'v': 1, 'deep': [{'k': '}'}]}), ('b', {'v': ']'})])
        self.assertEqual(list(jsonslicer.JsonSlicer(io.BytesIO(doc), ('tail', None))), [True, False])
        self.assertEqual(list(jsonslicer.JsonSlicer(io.BytesIO(doc), ('meta', 'x', 2, None))), ['z'])
        self.assertEqual(list(jsonslicer.JsonSlicer(io.BytesIO(doc), ('meta', 'n', None))), [])
        self.assertEqual(list(jsonslicer.JsonSlicer(io.BytesIO(b'{}'), (None,))), [])
        self.assertEqual(list(jsonslicer.JsonSlicer(io.BytesIO(b'[]'), (None,))), [])

    def test_malformed_document_raises(self):
        with self.assertRaises(ValueError):
            list(jsonslicer.JsonSlicer(io.BytesIO(b'{"a": 1 "b": 2}'), (None,)))


class HttpHeaders(unittest.TestCase):
    def test_last_response_of_a_redirect_chain_wins(self):
        text = (
            'HTTP/1.1 301 Moved Permanently\r\nLocation: /new\r\n\r\n'
            'HTTP/2 200\r\nContent-Type: text/plain\r\nLast-Modified: Sat, 27 Sep 2026 10:00:00 GMT\r\n\r\n'
        )
        status, headers = http._parse_headers(text)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get('last-modified'), 'Sat, 27 Sep 2026 10:00:00 GMT')
        self.assertEqual(headers['Content-Type'], 'text/plain')
        self.assertIn('LAST-MODIFIED', headers)
        self.assertIsNone(headers.get('etag'))

    def test_not_modified(self):
        status, headers = http._parse_headers('HTTP/1.1 304 Not Modified\r\nDate: x\r\n\r\n')
        self.assertEqual(status, 304)

    def test_none_headers_are_dropped_and_socks_is_optional(self):
        # Assemble the command through a fake run to see the argv.
        seen = {}

        class Result:
            returncode = 0
            stdout = b'HTTP/1.1 200 OK\r\nX: y\r\n\r\n'
            stderr = b''

        def fake_run(cmd, **kwargs):
            seen['cmd'] = cmd
            seen['input'] = kwargs.get('input')
            return Result()

        with unittest.mock.patch.object(http.subprocess, 'run', fake_run), \
                unittest.mock.patch.dict(http.os.environ, {'REPOLOGY_SOCKS5': '127.0.0.1:8015'}):
            status, headers = http._curl('https://x/y', None, {'Accept-Encoding': None, 'If-Modified-Since': 'z'}, 'body', 60, '/dev/null')

        cmd = seen['cmd']
        self.assertEqual(status, 200)
        self.assertEqual(cmd[-1], 'https://x/y')
        self.assertIn('--socks5-hostname', cmd)
        self.assertIn('If-Modified-Since: z', cmd)
        self.assertFalse(any(a.startswith('Accept-Encoding') for a in cmd))
        self.assertEqual(seen['input'], b'body')
        self.assertIn('--speed-time', cmd)


class Record(unittest.TestCase):
    def test_record_keeps_only_present_fields(self):
        package = types.SimpleNamespace(
            repo='stalix_dev', subrepo=None, srcname='lib/zlib', binname=None, binnames=None,
            visiblename='zlib', version='1.3.1', origversion='1.3.1', comment=None,
            category='lib', licenses=None, maintainers=['pg@x'],
        )
        self.assertEqual(
            repology.record(package, 'outdated'),
            {
                'repo': 'stalix_dev', 'srcname': 'lib/zlib', 'visiblename': 'zlib',
                'version': '1.3.1', 'origversion': '1.3.1', 'status': 'outdated',
                'categories': ['lib'], 'maintainers': ['pg@x'],
            },
        )

    def test_select_wants_a_package_of_ours(self):
        ours = types.SimpleNamespace(repo='stalix')
        theirs = types.SimpleNamespace(repo='arch')
        self.assertTrue(repology.select([theirs, ours]))
        self.assertFalse(repology.select([theirs]))

    def test_replace_once_rejects_missing_or_repeated_anchor(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'f.py'
            path.write_text('a\nb\na\n')

            with self.assertRaises(SystemExit):
                repology.replace_once(path, 'a\n', 'c\n')

            repology.replace_once(path, 'b\n', 'c\n')
            self.assertEqual(path.read_text(), 'a\nc\na\n')


if __name__ == '__main__':
    unittest.main()
