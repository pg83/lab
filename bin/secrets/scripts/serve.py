#!/usr/bin/env python3

import sys
import subprocess

import http.server as hs


CACHE = {}


def get_secret_1(path):
    path = path.replace('/', '_').replace('.', '_').replace('_neb', 'neb')

    with open('/sys/firmware/efi/efivars/' + path + '-f299ef14-61d1-4bf0-bfbc-565af88df0c9', 'rb') as f:
        return f.read()[4:]


def get_secret_2(path):
    return subprocess.check_output(['etcdctl', 'get', '--print-value-only', path])


def get_secret_3(path):
    return CACHE[path]


def get_secret_4(path):
    with open(path, 'rb') as f:
        return f.read()


def get_secret(path):
    for f in [get_secret_1, get_secret_2, get_secret_3, get_secret_4]:
        try:
            if res := f(path):
                CACHE[path] = res

                return res
        except Exception as e:
            print(f'while get {path}: {e}', file=sys.stderr)

    raise Exception(f'no such secret {path}')


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
