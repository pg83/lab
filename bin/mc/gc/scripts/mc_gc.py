#!/usr/bin/env python3

"""
Generic minio prefix GC: drop everything under <minio-path> whose
mtime is older than <hours>. Thin wrapper over

    mc rm --recursive --force --older-than=<H>h <path>

so mc does the listing + filtering itself.

Usage:
    mc_gc <minio-path> <hours>

Reads S3_ENDPOINT, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY from
env (same shape as bin/etcd/backup) and turns them into MC_HOST_minio
for the `minio` mc-alias.
"""

import os
import subprocess
import sys


REQUIRED_ENV = ('S3_ENDPOINT', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY')


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def mc_env(base):
    scheme, host = base['S3_ENDPOINT'].split('://', 1)
    env = dict(base)
    env['MC_HOST_minio'] = f"{scheme}://{base['AWS_ACCESS_KEY_ID']}:{base['AWS_SECRET_ACCESS_KEY']}@{host}"

    return env


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: mc_gc <minio-path> <hours>')

    for k in REQUIRED_ENV:
        if not os.environ.get(k):
            raise SystemExit(f'{k} not set')

    path = sys.argv[1].rstrip('/')
    # Refuse to operate on <alias> or <alias>/<bucket> alone — accidentally
    # GC-ing a whole bucket would be catastrophic. Need at minimum
    # <alias>/<bucket>/<prefix>.
    parts = path.split('/')

    if len(parts) < 3 or any(p == '' for p in parts):
        raise SystemExit(f'refusing {path!r}: need <alias>/<bucket>/<prefix...>, no empty segments')

    hours = int(sys.argv[2])

    log(f'mc_gc {path}: dropping entries older than {hours}h')
    subprocess.run(
        ['minio-client', 'rm', '--recursive', '--force', f'--older-than={hours}h', path],
        env=mc_env(os.environ),
        check=True,
    )


if __name__ == '__main__':
    main()
