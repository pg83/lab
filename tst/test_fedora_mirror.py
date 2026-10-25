"""Exercise the inline Fedora mirror over HTTP without external repositories."""

import contextlib
import hashlib
import http.client
import io
import pathlib
import sys
import tempfile
import threading
import types
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from email.utils import formatdate
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'lab'))
import cg


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {}


class MemoryS3:
    def __init__(self):
        self.objects = {}
        self.failed = False

    def __call__(self, key, method='GET', data=None, headers=None):
        if self.failed:
            raise urllib.error.HTTPError(key, 503, 'unavailable', {}, None)
        if method == 'PUT':
            self.objects[key] = (data.read(), formatdate(usegmt=True))
            return Response(b'')
        if key not in self.objects:
            return None
        data, stamp = self.objects[key]
        result = {'Content-Length': str(len(data)), 'Last-Modified': stamp,
                  'ETag': '"' + sha(data) + '"', 'Accept-Ranges': 'bytes'}
        status = 200
        if method != 'HEAD' and headers and 'Range' in headers:
            start, end = headers['Range'].removeprefix('bytes=').split('-')
            start, end = int(start), int(end)
            result['Content-Range'] = f'bytes {start}-{end}/{len(data)}'
            data = data[start:end + 1]
            result['Content-Length'] = str(len(data))
            status = 206
        return Response(b'' if method == 'HEAD' else data, status, result)


class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryS3()
        self.app = cg.FedoraMirror(0, 'http://localhost', 'http://s3:8093', '127.0.0.1:8015')
        self.app.s3 = self.store
        self.server = self.app.server('127.0.0.1')
        self.app.public_url = f'http://127.0.0.1:{self.server.server_port}'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.primary = b'compressed primary metadata'
        self.primary_path = f'repodata/{sha(self.primary)}-primary.xml.zst'
        self.rpm_path = 'Packages/m/mc-1.x86_64.rpm'
        self.rpm = b'example complete RPM contents'
        self.make_generation('first')
        self.calls = []
        self.fail_direct = False
        self.fail_all = False
        self.bad_first = False
        self.patcher = patch.object(cg.subprocess, 'run', side_effect=self.curl)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def make_generation(self, revision):
        self.repomd = f'''<repomd xmlns="http://linux.duke.edu/metadata/repo">
          <revision>{revision}</revision><data type="primary">
          <checksum type="sha256">{sha(self.primary)}</checksum>
          <location href="{self.primary_path}"/></data></repomd>'''.encode()
        self.digest = sha(self.repomd)
        self.discovery = f'''<metalink xmlns="http://www.metalinker.org/"
          xmlns:mm="http://fedorahosted.org/mirrormanager"><files><file name="repomd.xml">
          <verification><hash type="sha256">{self.digest}</hash></verification>
          <resources><url>https://one.example/repo/repodata/repomd.xml</url>
          <url>https://two.example/repo/repodata/repomd.xml</url></resources>
          <mm:alternates><mm:alternate><resources><url>https://old.example/repo</url>
          </resources></mm:alternate></mm:alternates></file></files></metalink>'''.encode()

    def curl(self, cmd, stdout, **kwargs):
        route = cmd[cmd.index('--proxy') + 1]
        url = cmd[-1]
        self.calls.append((route, url))
        if self.fail_all or self.fail_direct and not route:
            stdout.write(b'partial transfer')
            return types.SimpleNamespace(returncode=18, stderr=b'partial transfer')
        if url.startswith('https://mirrors.fedoraproject.org/metalink?'):
            body = self.discovery
        elif url.endswith('/repodata/repomd.xml'):
            body = self.repomd
        elif url.endswith(self.primary_path):
            body = self.primary
        elif url.endswith(self.rpm_path):
            body = self.rpm
        else:
            raise AssertionError(url)
        if self.bad_first:
            body = b'wrong checksum'
            self.bad_first = False
        stdout.write(body)
        return types.SimpleNamespace(returncode=0, stderr=b'')

    def request(self, path, method='GET', headers=None):
        with contextlib.closing(http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)) as conn:
            conn.request(method, path, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()

    def discover(self):
        status, _, body = self.request('/metalink?repo=fedora-44&arch=x86_64&countme=1')
        self.assertEqual(status, 200)
        root = ET.fromstring(body)
        urls = [e.text for e in root.findall('.//m:url', self.app.ns)]
        self.assertEqual(urls, [self.app.public_url + self.path('repodata/repomd.xml')])
        return body

    def path(self, path, digest=None):
        return f'/fedora-44/x86_64/{digest or self.digest}/{path}'

    def test_populates_s3_and_reuses_packages_and_metadata(self):
        self.assertEqual(self.app.s3_endpoint, 'http://s3:8093/fedora')
        self.discover()
        for path, expected in [('repodata/repomd.xml', self.repomd),
                               (self.primary_path, self.primary), (self.rpm_path, self.rpm)]:
            status, headers, body = self.request(self.path(path))
            self.assertEqual((status, headers['X-Cache'], body), (200, 'MISS', expected))
            n = len(self.calls)
            status, headers, body = self.request(self.path(path))
            self.assertEqual((status, headers['X-Cache'], body), (200, 'HIT', expected))
            self.assertEqual(len(self.calls), n)
        n = len(self.calls)
        self.discover()
        self.assertEqual(len(self.calls), n)
        self.assertTrue(all(not route for route, _ in self.calls))

    def test_new_metadata_keeps_old_snapshot_and_shares_rpms(self):
        self.discover()
        self.request(self.path('repodata/repomd.xml'))
        self.request(self.path(self.rpm_path))
        old_digest, old_repomd = self.digest, self.repomd
        self.make_generation('second')
        key = 'fedora-44/x86_64/metalink.xml'
        self.store.objects[key] = (self.store.objects[key][0], formatdate(0, usegmt=True))
        self.discover()
        status, _, body = self.request(self.path('repodata/repomd.xml'))
        self.assertEqual((status, body), (200, self.repomd))
        status, _, body = self.request(self.path('repodata/repomd.xml', old_digest))
        self.assertEqual((status, body), (200, old_repomd))
        n = len(self.calls)
        status, headers, body = self.request(self.path(self.rpm_path))
        self.assertEqual((status, headers['X-Cache'], body), (200, 'HIT', self.rpm))
        self.assertEqual(len(self.calls), n)

    def test_direct_mirrors_then_shared_proxy(self):
        self.fail_direct = True
        with tempfile.TemporaryFile() as tmp:
            self.app.download(['https://one.example/' + self.rpm_path,
                               'https://two.example/' + self.rpm_path], tmp)
            self.assertEqual(tmp.read(), self.rpm)
        self.assertEqual([route for route, _ in self.calls], ['', '', 'socks5h://127.0.0.1:8015'])

    def test_bad_checksum_is_retried_before_caching(self):
        self.discover()
        self.bad_first = True
        status, _, body = self.request(self.path('repodata/repomd.xml'))
        self.assertEqual((status, body), (200, self.repomd))
        self.assertEqual(self.app.counts['download_failures_total'], 1)

    def test_invalid_metalink_uses_proxy_fallback(self):
        self.bad_first = True
        self.discover()
        self.assertEqual([route for route, _ in self.calls], ['', 'socks5h://127.0.0.1:8015'])

    def test_partial_download_is_not_cached(self):
        self.discover()
        self.fail_all = True
        status, _, _ = self.request(self.path(self.rpm_path))
        self.assertEqual(status, 503)
        key = self.app.file_key('fedora-44', 'x86_64', self.digest, self.rpm_path)
        self.assertNotIn(key, self.store.objects)

    def test_head_range_and_conditional_get(self):
        self.discover()
        path = self.path(self.rpm_path)
        status, headers, body = self.request(path, headers={'Range': 'bytes=2-7'})
        self.assertEqual((status, body), (206, self.rpm[2:8]))
        status, headers, body = self.request(path, 'HEAD')
        self.assertEqual((status, int(headers['Content-Length']), body), (200, len(self.rpm), b''))
        status, _, body = self.request(path, headers={'If-None-Match': headers['ETag']})
        self.assertEqual((status, body), (304, b''))
        status, _, body = self.request(path, headers={'Range': 'bytes=0-1,4-5'})
        self.assertEqual((status, body), (200, self.rpm))

    def test_s3_failure_does_not_become_a_cache_miss(self):
        self.store.failed = True
        status, _, _ = self.request(self.path(self.rpm_path))
        self.assertEqual(status, 503)
        self.assertEqual(self.calls, [])

    def test_rejects_non_repository_paths(self):
        for path in ('Packages/../secret', 'Packages/%2e%2e/secret',
                     'Packages//secret', 'Packages/%5csecret', 'http://example.com/file'):
            with self.subTest(path=path):
                status, _, _ = self.request(self.path(path))
                self.assertEqual(status, 404)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
