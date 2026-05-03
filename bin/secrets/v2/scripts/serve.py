#!/usr/bin/env python3
"""
secrets_v2 — serve secrets from a git-committed encrypted JSONlines
blob, decrypted once on startup with a passphrase passed in via the
SECRETS_V2_MASTER_KEY env var.

Argv:
    1. listen port
    2. path to the encrypted store file

The parent (SecretsV2.run() in cg.py) runs as root, fetches
/master.key from EFI via `persdb get`, and injects it here through
the environment so the server itself runs unprivileged.

Format matches secrets/store (the original `mod` bicycle):
    outer: {"salt": "<hex>", "data": "<base64(lzma(aes-128-cbc(...)))>"}
    plaintext inside: jsonlines of {"k": "/some/path", "v": "value"}

The passphrase is combined with the per-file salt via openssl's
PBKDF2 KDF to derive the actual AES key+iv — byte-for-byte matching
secrets/mod so a file written by either tool opens with the other.

No TTL-recycle — keep the process running indefinitely. To rotate
secrets: edit store locally with mod, push to lab repo, next ix mut
replaces the file and pid1 respawns via _hash rotation.
"""

import os
import sys
import json
import base64
import lzma
import subprocess

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


def load_store(store_path, passphrase):
    raw = open(store_path).read()
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
    store_path = sys.argv[2]

    pp = os.environ['SECRETS_V2_MASTER_KEY'].strip()

    store = load_store(store_path, pp)

    print(f'secrets_v2: loaded {len(store)} keys from {store_path}', file=sys.stderr)

    etcd_cache = {}

    def get_etcd(path):
        if path in etcd_cache:
            return etcd_cache[path]

        out = subprocess.check_output(['etcdctl', 'get', '--print-value-only', path])
        etcd_cache[path] = out

        return out

    class Handler(hs.BaseHTTPRequestHandler):
        def do_GET(self):
            v = store.get(self.path)

            if v is not None:
                body = v.encode() if isinstance(v, str) else v
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.send_header('Content-length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

                return

            try:
                body = get_etcd(self.path)
            except Exception as e:
                self.send_error(404, message=str(e))

                return

            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Content-length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            sys.stderr.write(f'{self.client_address[0]} - - [{self.log_date_time_string()}] {fmt % args}\n')

    hs.ThreadingHTTPServer(('localhost', port), Handler).serve_forever()


if __name__ == '__main__':
    main()
