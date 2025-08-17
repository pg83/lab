#!/usr/bin/env python3

import sys
import json
import time
import base64
import subprocess

import http.server as hs
import urllib.request as ur


CACHE = {}


def get_secret_1(path):
    req = {
        'type': 'get',
        'key': path,
    }

    return ur.urlopen('http://localhost:8024/' + base64.b64encode(json.dumps(req).encode()).decode()).read()


def get_secret_2(path):
    return subprocess.check_output(['etcdctl', 'get', '--print-value-only', path])


def get_secret_3(path):
    with open(path, 'rb') as f:
        return f.read()


def get_secret_impl(path):
    for f in [get_secret_1, get_secret_2, get_secret_3]:
        try:
            if res := f(path):
                return res
        except Exception as e:
            print(f'while get {path}: {e}', file=sys.stderr)

    raise Exception(f'no such secret {path}')


def get_secret(path):
    k = path

    while True:
        try:
            return CACHE[k]
        except KeyError:
            CACHE[k] = get_secret_impl(path)


class Handler(hs.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            res, code = get_secret(self.path), 200
        except Exception as e:
            self.send_error(404, message=str(e))

            return

        self.send_response(code)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(res)


if __name__ == '__main__':
    hs.ThreadingHTTPServer(('localhost', int(sys.argv[1])), Handler).serve_forever()
