#!/usr/bin/env python3

import sys
import subprocess

import http.server as hs


def get_secret_1(path):
    with open(path.replace('/', '_').replace('.', '_').replace('_neb', 'neb'), 'rb') as f:
        return f.read()[4:]


def get_secret_2(path):
    return subprocess.check_output(['etcdctl', 'get', '--print-value-only', path])


def get_secret(path):
    for f in [get_secret_1, get_secret_2]:
        try:
            if res := f(path):
                return ret
        except Exception as e:
            print(e, file=sys.stderr)

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
