#!/usr/bin/env python3

"""
Pull every nebula secret from pers_db on each lab host and emit
jsonlines suitable for the secrets_v2 encrypted store:

    {"k": "/nebula/ca.crt",   "v": "-----BEGIN CERTIFICATE-----\\n..."}
    {"k": "/nebula/lab1.crt", "v": "..."}
    {"k": "/nebula/lab1.key", "v": "..."}
    ...

Each host's pers_db carries only the secrets that host actually used
(its own labN.crt/key + lhN.crt/key + the shared ca.crt), so we ssh
into each host separately and merge. ca.crt is identical everywhere,
fetched from lab1.

Usage:
    extract_nebula_secrets > plain.jsonl

Assumes key-based ssh root@<host>.nebula works and `persdb_get` is
in PATH on the host (it's shipped by lab/common).

Pipeline:
    extract_nebula_secrets > plain.jsonl
    # encrypt with your master passphrase using secrets/mod
    # commit the result to lab/bin/secrets/v2/scripts/store
"""

import json
import subprocess
import sys


# Each (host, lab-name, lh-name) — the two cert/key pairs this host's
# pers_db is expected to hold (via get_key -> old secrets -> pers_db
# caching on first use from NebulaNode / NebulaLh run()).
HOSTS = [
    ('lab1', 'lab1', 'lh1'),
    ('lab2', 'lab2', 'lh2'),
    ('lab3', 'lab3', 'lh3'),
]


def fetch(host, key):
    out = subprocess.check_output([
        'ssh', f'root@{host}.nebula',
        f'persdb_get {key}',
    ])

    return out.decode('utf-8')


def emit(k, v):
    sys.stdout.write(json.dumps({'k': k, 'v': v}))
    sys.stdout.write('\n')
    sys.stdout.flush()


def main():
    # ca is shared — take it from lab1's pers_db.
    emit('/nebula/ca.crt', fetch('lab1', '/nebula/ca.crt'))

    for host, lab_name, lh_name in HOSTS:
        for name in (lab_name, lh_name):
            for suffix in ('crt', 'key'):
                k = f'/nebula/{name}.{suffix}'
                emit(k, fetch(host, k))


if __name__ == '__main__':
    main()
