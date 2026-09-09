import contextlib
import hashlib
import http.client
import importlib.util
import io
import json
import stat
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('artifacts', Path(__file__).resolve().parents[1] / 'lab/artifacts.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def bundle(entries=None):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in (entries or [('index.html', '<h1>hello</h1>'), ('assets/main.mjs', 'export const x=1;')]):
            z.writestr(name, data)
    return out.getvalue()


class MemoryStore:
    def __init__(self, cache):
        self.cache = cache
        self.data = {}

    def put(self, sha, file):
        self.data[sha] = file.read()

    @contextlib.contextmanager
    def archive(self, sha):
        if sha not in self.data:
            raise app.Missing()
        with zipfile.ZipFile(io.BytesIO(self.data[sha])) as z:
            yield z


class ValidationTests(unittest.TestCase):
    def test_valid_archive(self):
        src = io.BytesIO(bundle())
        app.validate_zip(src)
        self.assertEqual(src.tell(), 0)

    def test_rejects_paths(self):
        for name in ('../evil', '/evil', 'a/../evil', 'a//evil', 'a\\evil', './evil'):
            with self.subTest(name=name), self.assertRaises(app.BadRequest):
                app.validate_zip(io.BytesIO(bundle([('index.html', 'ok'), (name, 'bad')])))

    def test_requires_root_index(self):
        with self.assertRaises(app.BadRequest):
            app.validate_zip(io.BytesIO(bundle([('site/index.html', 'ok')])))

    def test_rejects_symlink(self):
        link = zipfile.ZipInfo('evil')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(app.BadRequest):
            app.validate_zip(io.BytesIO(bundle([('index.html', 'ok'), (link, '/etc/passwd')])))

    def test_rejects_bomb_and_bad_zip(self):
        with patch.object(app, 'MAX_FILE', 8), self.assertRaises(app.BadRequest):
            app.validate_zip(io.BytesIO(bundle()))
        with self.assertRaises(app.BadRequest):
            app.validate_zip(io.BytesIO(b'not zip'))

    def test_rejects_file_directory_collision(self):
        with self.assertRaises(app.BadRequest):
            app.validate_zip(io.BytesIO(bundle([('index.html', 'ok'), ('a', 'x'), ('a/b', 'y')])))


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(self.temp.name)
        self.servers = [app.Server(('127.0.0.1', 0), self.store, 'https://view.homelab.cam', upload=u)
                        for u in (False, True)]
        for s in self.servers:
            threading.Thread(target=s.serve_forever, daemon=True).start()

    def tearDown(self):
        for s in self.servers:
            s.shutdown()
            s.server_close()
        self.temp.cleanup()

    def request(self, method, path, data=None, headers=None, upload=False):
        conn = http.client.HTTPConnection(*self.servers[int(upload)].server_address, timeout=5)
        conn.request(method, path, data, headers or {})
        resp = conn.getresponse()
        result = resp.status, dict(resp.getheaders()), resp.read()
        conn.close()
        return result

    def publish(self, data=None):
        data = bundle() if data is None else data
        status, headers, body = self.request('POST', '/api/artifacts', data,
                                             {'X-Artifact-Upload': '1'}, upload=True)
        self.assertEqual(status, 201, body)
        doc = json.loads(body)
        self.assertEqual(doc['sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(self.store.data[doc['sha256']], data)
        return '/view/' + doc['sha256']

    def test_upload_hash_idempotency_and_view(self):
        data = bundle()
        path = self.publish(data)
        self.assertEqual(self.publish(data), path)
        self.assertEqual(len(self.store.data), 1)
        status, headers, body = self.request('GET', path)
        self.assertEqual(status, 308)
        self.assertEqual(headers['Location'], path + '/')
        status, headers, body = self.request('GET', path + '/')
        self.assertEqual((status, body), (200, b'<h1>hello</h1>'))
        self.assertEqual(headers['Cache-Control'], app.IMMUTABLE)
        self.assertIn('sandbox allow-scripts', headers['Content-Security-Policy'])
        self.assertNotIn('allow-same-origin', headers['Content-Security-Policy'])
        self.assertEqual(self.request('GET', path + '/', headers={'If-None-Match': headers['ETag']})[0], 304)
        self.assertEqual(self.request('HEAD', path + '/')[2], b'')
        status, headers, body = self.request('GET', path + '/assets/main.mjs')
        self.assertEqual(status, 200)
        self.assertIn('text/javascript', headers['Content-Type'])
        self.assertEqual(headers['Access-Control-Allow-Origin'], '*')

    def test_no_listing_and_errors_not_cached(self):
        path = self.publish()
        for route in ('/', '/view/', '/api/artifacts', path + '/assets/', path + '/missing', '/view/' + '0'*64 + '/'):
            with self.subTest(route=route):
                status, headers, body = self.request('GET', route)
                self.assertEqual(status, 404)
                self.assertEqual(headers['Cache-Control'], 'no-store')

    def test_encoded_traversal(self):
        path = self.publish()
        for name in ('../index.html', '%2e%2e/index.html', '%2findex.html', 'a%5cb'):
            self.assertEqual(self.request('GET', path + '/' + name)[0], 404)

    def test_upload_not_public_and_no_browser_cross_origin(self):
        for headers, private, expected in (({'X-Artifact-Upload': '1'}, False, 404),
                                            ({}, True, 403),
                                            ({'X-Artifact-Upload': '1', 'Origin': 'null'}, True, 403)):
            self.assertEqual(self.request('POST', '/api/artifacts', bundle(), headers, upload=private)[0], expected)

    def test_bad_upload_never_published(self):
        status, _, _ = self.request('POST', '/api/artifacts', b'bad', {'X-Artifact-Upload': '1'}, upload=True)
        self.assertEqual(status, 400)
        self.assertEqual(self.store.data, {})

    def test_nested_index_redirect(self):
        path = self.publish(bundle([('index.html', 'home'), ('docs/index.html', 'docs')]))
        self.assertEqual(self.request('GET', path + '/docs')[0], 308)
        self.assertEqual(self.request('GET', path + '/docs/')[2], b'docs')


if __name__ == '__main__':
    unittest.main()
