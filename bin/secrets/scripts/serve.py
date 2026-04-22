#!/usr/bin/env python3

import sys
import subprocess

import http.server as hs


CACHE = {}


def get_secret_impl(path):
    return subprocess.check_output(['etcdctl', 'get', '--print-value-only', path])


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
