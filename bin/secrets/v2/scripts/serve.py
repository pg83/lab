#!/usr/bin/env python3
"""
secrets_v2 — serve secrets from a git-committed encrypted JSONlines
blob, decrypted once on startup with a passphrase pulled from pers_db.

Argv:
    1. listen port
    2. persdb port
    3. path to the encrypted store file

Format matches secrets/store (the original `mod` bicycle):
    outer: {"salt": "<hex>", "data": "<base64(lzma(aes-128-cbc(...)))>"}
    plaintext inside: jsonlines of {"k": "/some/path", "v": "value"}

The passphrase (stored as a raw utf-8 string under pers_db key
"/master.key") is combined with the per-file salt via openssl's
PBKDF2 KDF to derive the actual AES key+iv — byte-for-byte matching
secrets/mod so a file written by either tool opens with the other.

The decrypted store sits in process memory until the service restarts.
No TTL-recycle — keep the process running indefinitely. To rotate
secrets: edit store locally with mod-style CLI, push to lab repo,
next ix mut replaces the file and pid1 respawns the service.
"""

import os
import sys
import json
import base64
import lzma
import subprocess
import urllib.request as ur

import http.server as hs


AES = '-aes-128-cbc'


def runbin(cmd, input):
    return subprocess.check_output(cmd, input=input)


def runtext(cmd):
    return runbin(cmd, None).decode()


def genkey(pp, salt):
    out = runtext([
        'openssl', 'enc', '-pbkdf2', AES,
        '-k', pp, '-P', '-S', salt,
    ])

    res = {}

    for l in out.splitlines():
        l = l.strip()

        if not l:
            continue

        a, b = l.split('=')

        res[a.strip()] = b.strip()

    return res


def decode(key, iv, data):
    return runbin(
        ['openssl', 'enc', AES, '-K', key, '-iv', iv, '-d'],
        data,
    )


def persdb_get(persdb_port, key):
    req = {'type': 'get', 'key': key}
    q = base64.b64encode(json.dumps(req).encode()).decode()
    return ur.urlopen(f'http://localhost:{persdb_port}/{q}').read()


def load_store(store_path, passphrase):
    try:
        raw = open(store_path).read()
    except FileNotFoundError:
        print(f'secrets_v2: store {store_path} not found; serving empty', file=sys.stderr)
        return {}

    if not raw.strip():
        print(f'secrets_v2: store {store_path} empty; serving empty', file=sys.stderr)
        return {}

    d = json.loads(raw)
    k = genkey(passphrase, d['salt'])
    ct = base64.b64decode(d['data'])
    pt = lzma.decompress(decode(k['key'], k['iv'], ct))

    out = {}

    for line in pt.splitlines():
        line = line.strip()

        if not line:
            continue

        e = json.loads(line)
        out[e['k']] = e['v']

    return out


def main():
    port = int(sys.argv[1])
    persdb_port = int(sys.argv[2])
    store_path = sys.argv[3]

    pp = persdb_get(persdb_port, '/master.key').decode('utf-8').strip()

    store = load_store(store_path, pp)

    print(f'secrets_v2: loaded {len(store)} keys from {store_path}', file=sys.stderr)

    class Handler(hs.BaseHTTPRequestHandler):
        def do_GET(self):
            v = store.get(self.path)

            if v is None:
                self.send_error(404, 'no such secret')
                return

            body = v.encode() if isinstance(v, str) else v
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Content-length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            # mirror old secrets service's noisy default logging
            sys.stderr.write(f'{self.client_address[0]} - - [{self.log_date_time_string()}] {fmt % args}\n')

    hs.ThreadingHTTPServer(('localhost', port), Handler).serve_forever()


if __name__ == '__main__':
    main()
