#!/usr/bin/env python3

import os
import sys
import json
import base64
import hashlib
import contextlib
import subprocess

import http.server as hs


UUID = 'f299ef14-61d1-4bf0-bfbc-565af88df0c9'


def hash_key(key):
    return hashlib.md5(key.encode()).hexdigest()


def serve_get(req):
    cmd = [
        'unshare',
        '-m',
        'efi_get',
        hash_key(req['key']),
        UUID,
    ]

    return subprocess.check_output(cmd)[4:]


@contextlib.contextmanager
def memfd(name):
    fd = os.memfd_create(name, flags=0)

    try:
        yield f'/proc/{os.getpid()}/fd/{fd}'
    finally:
        os.close(fd)


def serve_put(req):
    with memfd('value') as path:
        with open(path, 'wb') as f:
            f.write(base64.b64decode(req['val']))

        cmd = [
            'unshare',
            '-m',
            'efi_put',
            hash_key(req['key']),
            UUID,
            path,
        ]

        return subprocess.check_output(cmd)


def serve(data):
    req = json.loads(data)

    if req['type'] == 'get':
        return serve_get(req)

    if req['type'] == 'put':
        return serve_put(req)

    raise Exception('unknown request type ' + req['type'])


class Handler(hs.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            res, code = serve(base64.b64decode(self.path.split('/')[-1])), 200
        except Exception as e:
            self.send_error(404, message=str(e))
            return

        self.send_response(code)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

        if res:
            self.wfile.write(res)


if __name__ == '__main__':
    hs.ThreadingHTTPServer(('localhost', int(sys.argv[1])), Handler).serve_forever()
