#!/usr/bin/env python3
"""ZIP CAS hosting. POST a ZIP to /api/artifacts; GET /view/<sha256>/path.

No catalog, extraction, database, or server-side execution. The upload listener
is private; the public listener only serves immutable files from validated ZIPs.
Requires minio-client and MC_HOST_view (credentials for the view bucket).
"""

import argparse
import collections
import contextlib
import hashlib
import http.server
import json
import mimetypes
import os
import re
import signal
import stat
import subprocess
import tempfile
import threading
import urllib.parse
import zipfile
import zlib
from pathlib import Path


MAX_ZIP = 64 * 1024 * 1024
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_ENTRIES = 4096
CACHE_ENTRIES = 8
IMMUTABLE = 'public, max-age=315360000, immutable'
SHA = re.compile(r'[0-9a-f]{64}')


class BadRequest(Exception):
    pass


class Missing(Exception):
    pass


class StorageError(Exception):
    pass


def safe_path(name):
    return (bool(name) and not name.startswith('/') and '\\' not in name
            and not any(ord(c) < 32 or ord(c) == 127 for c in name)
            and all(p not in ('', '.', '..') for p in name.rstrip('/').split('/')))


def validate_zip(file):
    """Check every member and CRC before publishing; never extract paths."""
    try:
        with zipfile.ZipFile(file) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ENTRIES:
                raise BadRequest('too many ZIP entries')
            names = set()
            total = 0
            for entry in entries:
                name = entry.filename
                kind = stat.S_IFMT(entry.external_attr >> 16)
                if (not safe_path(name) or name.rstrip('/') in names
                        or kind not in (0, stat.S_IFREG, stat.S_IFDIR)
                        or entry.flag_bits & 1
                        or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise BadRequest('unsafe, duplicate, encrypted, or unsupported ZIP entry')
                names.add(name.rstrip('/'))
                total += entry.file_size
                if entry.file_size > MAX_FILE or total > MAX_TOTAL:
                    raise BadRequest('uncompressed ZIP size limit exceeded')
                with archive.open(entry) as src:
                    size = 0
                    while chunk := src.read(65536):
                        size += len(chunk)
                        if size > MAX_FILE:
                            raise BadRequest('file size limit exceeded')
                if size != entry.file_size:
                    raise BadRequest('ZIP size mismatch')
            if 'index.html' not in names or archive.getinfo('index.html').is_dir():
                raise BadRequest('ZIP must contain index.html at its root')
            for name in names:
                parts = name.split('/')
                for i in range(1, len(parts)):
                    parent = '/'.join(parts[:i])
                    if parent in archive.NameToInfo and not archive.getinfo(parent).is_dir():
                        raise BadRequest('file/directory collision')
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error) as exc:
        raise BadRequest('invalid ZIP') from exc
    finally:
        file.seek(0)


class Store:
    def __init__(self, cache):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.recent = collections.OrderedDict()

    def mc(self, *args, **kwargs):
        # Never log the credential-bearing environment or mc stderr.
        try:
            proc = subprocess.run(['minio-client', *args], stderr=subprocess.PIPE,
                                  timeout=120, **kwargs)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise StorageError('storage unavailable') from exc
        if proc.returncode:
            raise StorageError('storage request failed')
        return proc

    def put(self, sha, file):
        # subprocess reads the OS descriptor, not Python's buffered position.
        # zipfile validation may leave that descriptor at EOF despite seek(0).
        file.flush()
        os.lseek(file.fileno(), 0, os.SEEK_SET)
        # Same key always gets the exact same bytes: idempotent CAS publication.
        self.mc('pipe', 'view/view/' + sha, stdin=file, stdout=subprocess.DEVNULL)

    @contextlib.contextmanager
    def archive(self, sha):
        with self.lock:
            path = self.recent.get(sha)
            if path is None:
                # Stat distinguishes a missing object from a storage outage.
                try:
                    proc = subprocess.run(['minio-client', 'stat', '--json', 'view/view/' + sha],
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    raise StorageError('storage unavailable') from exc
                if proc.returncode:
                    try:
                        cause = json.loads(proc.stdout).get('error', {}).get('cause', {})
                        code = cause.get('error', {}).get('Code')
                        missing = cause.get('message') == 'Object does not exist'
                    except (ValueError, AttributeError):
                        code = None
                        missing = False
                    if missing or code in ('NoSuchKey', 'NoSuchObject', 'NotFound'):
                        raise Missing()
                    raise StorageError('storage request failed')
                info = json.loads(proc.stdout)
                if info.get('size', MAX_ZIP + 1) > MAX_ZIP:
                    raise StorageError('stored ZIP exceeds limit')
                with tempfile.NamedTemporaryFile(dir=self.cache, prefix='zip-', delete=False) as dst:
                    path = Path(dst.name)
                    try:
                        self.mc('cat', 'view/view/' + sha, stdout=dst)
                        dst.flush()
                        with path.open('rb') as src:
                            if path.stat().st_size > MAX_ZIP or hashlib.file_digest(src, 'sha256').hexdigest() != sha:
                                raise StorageError('stored ZIP checksum mismatch')
                    except BaseException:
                        path.unlink(missing_ok=True)
                        raise
                self.recent[sha] = path
                while len(self.recent) > CACHE_ENTRIES:
                    _, old = self.recent.popitem(last=False)
                    old.unlink(missing_ok=True)
            self.recent.move_to_end(sha)
            # Open under the lock; POSIX keeps the file readable after eviction.
            archive = zipfile.ZipFile(path)
        try:
            yield archive
        finally:
            archive.close()


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, store, public_url, upload=False):
        self.store = store
        self.public_url = public_url.rstrip('/')
        self.upload = upload
        self.capacity = threading.BoundedSemaphore(16)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.capacity.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.capacity.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.capacity.release()


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'view/1'

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def reply(self, status, body=b'', content_type='text/plain; charset=utf-8', headers=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', (headers or {}).get('Cache-Control', 'no-store'))
        for key, value in (headers or {}).items():
            if key != 'Cache-Control':
                self.send_header(key, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            self.get()
        except Missing:
            self.reply(404, b'not found\n')
        except (StorageError, zipfile.BadZipFile, OSError):
            self.reply(503, b'storage unavailable\n')

    def get(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == '/healthz':
            self.reply(200, b'ok\n')
            return
        parts = path.split('/', 3)
        if len(parts) < 3 or parts[1] != 'view' or not SHA.fullmatch(parts[2]):
            raise Missing()
        sha = parts[2]
        try:
            name = urllib.parse.unquote(parts[3], errors='strict') if len(parts) == 4 else ''
        except UnicodeError:
            raise Missing()
        if name and not safe_path(name):
            raise Missing()
        with self.server.store.archive(sha) as archive:
            if len(parts) == 3:
                self.reply(308, headers={'Location': path + '/', 'Cache-Control': IMMUTABLE})
                return
            if not name or name.endswith('/'):
                name += 'index.html'
            try:
                entry = archive.getinfo(name)
            except KeyError:
                # Only index.html directories are navigable; never list files.
                if not name.endswith('/') and name + '/index.html' in archive.NameToInfo:
                    self.reply(308, headers={'Location': path + '/', 'Cache-Control': IMMUTABLE})
                    return
                raise Missing()
            if entry.is_dir() or entry.file_size > MAX_FILE:
                raise Missing()
            etag = '"' + hashlib.sha256((sha + '/' + name).encode()).hexdigest() + '"'
            headers = {
                'Cache-Control': IMMUTABLE,
                'Cloudflare-CDN-Cache-Control': IMMUTABLE,
                'ETag': etag,
                'Access-Control-Allow-Origin': '*',
                # Opaque origins isolate artifacts from each other and the lab.
                # CORS above lets ES modules/fonts load inside the sandbox.
                'Content-Security-Policy': "sandbox allow-scripts allow-downloads; base-uri 'self'; object-src 'none'",
            }
            if self.headers.get('If-None-Match') in (etag, '*'):
                self.reply(304, headers=headers)
                return
            body = archive.read(entry)
        kind = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        if name.endswith(('.js', '.mjs')):
            kind = 'text/javascript'
        if kind.startswith('text/'):
            kind += '; charset=utf-8'
        self.reply(200, body, kind, headers)

    def do_POST(self):
        if not self.server.upload or self.path != '/api/artifacts':
            self.reply(404, b'not found\n')
            return
        # CLI upload only, private listener. Cross-origin forms cannot supply
        # this header and we never authorize CORS preflight on the upload API.
        if self.headers.get('X-Artifact-Upload') != '1' or self.headers.get('Origin'):
            self.reply(403, b'CLI upload requires X-Artifact-Upload: 1 and no Origin\n')
            return
        try:
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                raise BadRequest('one Content-Length required; chunked uploads are not supported')
            length = int(self.headers['Content-Length'])
            if not 0 < length <= MAX_ZIP:
                self.reply(413, b'ZIP limit: 64 MiB\n')
                return
            with tempfile.TemporaryFile(dir=self.server.store.cache) as dst:
                digest = hashlib.sha256()
                remaining = length
                while remaining:
                    chunk = self.rfile.read(min(65536, remaining))
                    if not chunk:
                        raise BadRequest('incomplete upload')
                    dst.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
                dst.seek(0)
                validate_zip(dst)
                sha = digest.hexdigest()
                self.server.store.put(sha, dst)
            url = self.server.public_url + '/view/' + sha + '/'
            self.reply(201, json.dumps({'sha256': sha, 'url': url}).encode(),
                       'application/json', {'Location': url})
        except (BadRequest, ValueError) as exc:
            self.reply(400, (str(exc) + '\n').encode())
        except (StorageError, OSError):
            self.reply(503, b'storage unavailable\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8056)
    parser.add_argument('--upload-bind', required=True)
    parser.add_argument('--upload-port', type=int, default=8055)
    parser.add_argument('--public-url', default='https://view.homelab.cam')
    parser.add_argument('--cache-dir', default='.')
    args = parser.parse_args()
    if not os.environ.get('MC_HOST_view'):
        parser.error('MC_HOST_view is required')
    # A process-owned directory: no stale cache or partially downloaded ZIPs
    # survive normal shutdown. MinIO remains the only persistent source.
    with tempfile.TemporaryDirectory(prefix='view-cache-', dir=args.cache_dir) as cache:
        store = Store(cache)
        public = Server((args.bind, args.port), store, args.public_url)
        upload = Server((args.upload_bind, args.upload_port), store, args.public_url, upload=True)
        def stop(signum, frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, stop)
        thread = threading.Thread(target=upload.serve_forever, daemon=True)
        thread.start()
        print(f'view: serving {args.bind}:{args.port}; upload {args.upload_bind}:{args.upload_port}', flush=True)
        try:
            public.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            upload.shutdown()
            upload.server_close()
            public.server_close()


if __name__ == '__main__':
    main()
