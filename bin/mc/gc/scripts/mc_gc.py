#!/usr/bin/env python3

"""
Generic minio GC: drop top-level entries under <minio-path> whose
mtime is older than <hours>.

Listing is shallow — one `mc ls` of the prefix. The layout under
the prefix is assumed to be flat (one folder per task guid that
gets written all at once), so the folder's effective mtime is a
fair proxy for "when this artifact bundle finalised".

Usage:
    mc_gc <minio-path> <hours>

Reads S3_ENDPOINT, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY from
the environment — same env-shaped contract as bin/etcd/backup.
Fails loud if any are missing.
"""

import json
import os
import subprocess
import sys
import time


REQUIRED_ENV = ('S3_ENDPOINT', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY')


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def mc_env(base):
    scheme, host = base['S3_ENDPOINT'].split('://', 1)
    env = dict(base)
    env['MC_HOST_minio'] = f"{scheme}://{base['AWS_ACCESS_KEY_ID']}:{base['AWS_SECRET_ACCESS_KEY']}@{host}"

    return env


def parse_iso(s):
    # mc emits e.g. "2026-04-28T23:35:28.554247114Z"; strip fractional
    # seconds and the trailing Z, then strptime in UTC.
    s = s.split('.')[0].rstrip('Z')

    return int(time.mktime(time.strptime(s, '%Y-%m-%dT%H:%M:%S')))


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: mc_gc <minio-path> <hours>')

    for k in REQUIRED_ENV:
        if not os.environ.get(k):
            raise SystemExit(f'{k} not set')

    path = sys.argv[1].rstrip('/')
    # Belt-and-suspenders: refuse to operate on <alias> or <alias>/<bucket>
    # alone — accidentally GC-ing a whole bucket would be catastrophic.
    # Require <alias>/<bucket>/<at-least-one-key-component>.
    parts = path.split('/')

    if len(parts) < 3 or any(p == '' for p in parts):
        raise SystemExit(f'refusing {path!r}: need <alias>/<bucket>/<prefix...>, no empty segments')

    hours = int(sys.argv[2])
    cutoff = int(time.time()) - hours * 3600

    env = mc_env(os.environ)

    res = subprocess.run(
        ['minio-client', 'ls', '--json', path + '/'],
        env=env,
        check=True,
        stdout=subprocess.PIPE,
    )

    drops = []

    for line in res.stdout.decode().splitlines():
        if not line.strip():
            continue

        rec = json.loads(line)
        ts = rec.get('lastModified') or rec.get('time')

        if not ts:
            continue

        mtime = parse_iso(ts)

        if mtime >= cutoff:
            continue

        key = rec['key'].rstrip('/')

        if key:
            drops.append(key)

    log(f'mc_gc {path}: {len(drops)} entries older than {hours}h to drop')

    for key in drops:
        target = f'{path}/{key}'
        subprocess.run(
            ['minio-client', 'rm', '--recursive', '--force', target],
            env=env,
            check=True,
        )

    log(f'mc_gc {path}: done, dropped {len(drops)}')


if __name__ == '__main__':
    main()
