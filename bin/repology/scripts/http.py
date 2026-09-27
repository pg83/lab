"""
Replacement for repology/fetchers/http.py: the same do_http /
save_http_stream / PoliteHTTP / NotModifiedException surface, over the
curl binary instead of requests, brotli and zstandard.

curl speaks socks5 (REPOLOGY_SOCKS5, the lab's egress) and follows
redirects like requests did. The body goes to a temporary file, then
into the caller's file, decompressed if asked: gz/xz/bz2 with the
stdlib, br/zstd with the brotli and zstd binaries.
"""

import bz2
import functools
import gzip
import json as _json
import lzma
import os
import subprocess
import tempfile
import time

from repology.config import config

USER_AGENT = 'repology-fetcher/0 (+{}/docs/bots)'.format(config['REPOLOGY_HOME'])
STREAM_CHUNK_SIZE = 65536


class RequestException(Exception):
    pass


class HTTPError(RequestException):
    pass


class NotModifiedException(RequestException):
    def __init__(self, response=None):
        super().__init__('not modified')
        self.response = response


class Headers(dict):
    """Case-insensitive header lookup, the part of requests' structure callers use."""

    def __init__(self, items=()):
        super().__init__()

        for key, value in items:
            self[key] = value

    def __setitem__(self, key, value):
        super().__setitem__(key.lower(), value)

    def __getitem__(self, key):
        return super().__getitem__(key.lower())

    def __contains__(self, key):
        return super().__contains__(key.lower())

    def get(self, key, default=None):
        return super().get(key.lower(), default)


class Response:
    def __init__(self, url, status_code, headers, body_path):
        self.url = url
        self.status_code = status_code
        self.headers = headers
        self._body_path = body_path

    @property
    def content(self):
        with open(self._body_path, 'rb') as f:
            return f.read()

    @property
    def text(self):
        return self.content.decode('utf-8', errors='replace')

    def json(self):
        return _json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPError(f'{self.status_code} for {self.url}')

    def close(self):
        try:
            os.unlink(self._body_path)
        except FileNotFoundError:
            pass


def _parse_headers(text):
    # curl -D writes every response of a redirect chain; the last one counts.
    blocks = [b for b in text.replace('\r\n', '\n').split('\n\n') if b.strip()]
    lines = blocks[-1].split('\n')
    status = int(lines[0].split()[1])
    headers = Headers()

    for line in lines[1:]:
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip()] = value.strip()

    return status, headers


def _curl(url, method, headers, data, timeout, body_path):
    # --compressed: decode Content-Encoding like requests did (guix answers
    # gzip, nix brotli, whatever the client asks for).
    cmd = ['curl', '-sS', '-L', '--compressed', '-o', body_path, '-D', '-', '-A', USER_AGENT]

    socks = os.environ.get('REPOLOGY_SOCKS5')

    if socks:
        cmd += ['--socks5-hostname', socks]

    if timeout:
        # Bound the connect and a stalled transfer, not the transfer itself:
        # the big indices legitimately take minutes.
        cmd += ['--connect-timeout', str(timeout), '--speed-time', str(timeout), '--speed-limit', '1']

    for key, value in headers.items():
        if value is not None:
            cmd += ['-H', f'{key}: {value}']

    if method:
        cmd += ['-X', method]

    if data is not None:
        cmd += ['--data-binary', '@-']

    if isinstance(data, str):
        data = data.encode('utf-8')

    cmd.append(url)

    res = subprocess.run(cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if res.returncode != 0:
        raise RequestException(f'curl failed for {url}: {res.stderr.decode(errors="replace").strip()}')

    return _parse_headers(res.stdout.decode('latin-1'))


def do_http(url,
            method=None,
            check_status=True,
            timeout=5,
            data=None,
            json=None,
            post=None,
            headers=None,
            stream=False):
    headers = dict(headers) if headers else {}

    if post and not data:
        data = post

    if json and not data:
        data = _json.dumps(json)

    fd, body_path = tempfile.mkstemp(prefix='http.')
    os.close(fd)

    try:
        status, response_headers = _curl(url, method, headers, data, timeout, body_path)
    except BaseException:
        os.unlink(body_path)
        raise

    response = Response(url, status, response_headers, body_path)

    if check_status:
        response.raise_for_status()

    return response


def _copy(src, dst):
    while True:
        chunk = src.read(STREAM_CHUNK_SIZE)

        if not chunk:
            return

        dst.write(chunk)


def _decompress(compression, path, outfile):
    if compression == 'gz':
        with gzip.open(path) as f:
            _copy(f, outfile)
    elif compression == 'xz':
        with lzma.open(path) as f:
            _copy(f, outfile)
    elif compression == 'bz2':
        with bz2.open(path) as f:
            _copy(f, outfile)
    elif compression in ('br', 'zstd'):
        tool = ['brotli', '-d', '-c', path] if compression == 'br' else ['zstd', '-d', '-c', '-q', path]

        with subprocess.Popen(tool, stdout=subprocess.PIPE) as proc:
            _copy(proc.stdout, outfile)

        if proc.returncode != 0:
            raise RuntimeError(f'{tool[0]} failed with code {proc.returncode}')
    else:
        raise ValueError('Unsupported compression {}'.format(compression))


def save_http_stream(url, outfile, compression=None, **kwargs):
    kwargs.pop('stream', None)
    response = do_http(url, **kwargs)

    try:
        if response.status_code == 304:
            raise NotModifiedException(response=response)

        if compression is None:
            with open(response._body_path, 'rb') as f:
                _copy(f, outfile)
        else:
            _decompress(compression, response._body_path, outfile)
    finally:
        response.close()

    return response


class PoliteHTTP:
    def __init__(self, timeout=5, delay=None):
        self.do_http = functools.partial(do_http, timeout=timeout)
        self.delay = delay
        self.had_requests = False

    def __call__(self, *args, **kwargs):
        if self.had_requests and self.delay:
            time.sleep(self.delay)

        self.had_requests = True
        return self.do_http(*args, **kwargs)
