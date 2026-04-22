#!/usr/bin/env python3

"""
Pull every nebula secret out of the running secrets-v1 service on a
lab host and emit jsonlines suitable for the secrets_v2 encrypted
store. The output line format matches secrets_v2's load_store parser:

    {"k": "/nebula/ca.crt",  "v": "-----BEGIN CERTIFICATE-----\\n..."}
    {"k": "/nebula/lab1.crt", "v": "..."}
    {"k": "/nebula/lab1.key", "v": "..."}
    ...

Pipe the output through secrets/mod to produce a salt+ciphertext JSON:

    extract_nebula_secrets lab1 > plain.jsonl
    # edit with your passphrase through mod (or whatever tool),
    # then commit the result to lab/bin/secrets/v2/scripts/store

Any host in the cluster works — the legacy secrets cascade reaches
etcd so per-host certs are fetchable from anywhere.

Usage:
    extract_nebula_secrets [host]          # default lab1

Assumes key-based ssh root@<host>.nebula works.
"""

import json
import subprocess
import sys


HOSTS = ['lab1', 'lab2', 'lab3', 'lh1', 'lh2', 'lh3']


def iter_keys():
    yield '/nebula/ca.crt'

    for h in HOSTS:
        yield f'/nebula/{h}.crt'
        yield f'/nebula/{h}.key'


def fetch(host, key):
    # curl -f: fail (non-zero) on 4xx/5xx; -sS: silent body + show errors
    out = subprocess.check_output([
        'ssh', f'root@{host}.nebula',
        f'curl -fsS http://localhost:8022{key}',
    ])

    return out.decode('utf-8')


def main():
    fetch_host = sys.argv[1] if len(sys.argv) > 1 else 'lab1'

    for k in iter_keys():
        v = fetch(fetch_host, k)

        sys.stdout.write(json.dumps({'k': k, 'v': v}))
        sys.stdout.write('\n')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
