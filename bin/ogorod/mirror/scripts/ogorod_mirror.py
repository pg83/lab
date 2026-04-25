#!/usr/bin/env python3

"""
Mirror github.com/pg83/<r> → http://127.0.0.1:8035/mirror_<r>.git
under /lock/ogorod/mirror/<r>, fired every 10s by job_scheduler.
The repo name is the only argv: the cron generator emits one entry
per repo so each sync runs on its own lock.

ls-remote both upstream and our mirror, sort, compare. Equality
(the common case) means an early return — the whole tick is two
cheap HTTPS round-trips and no I/O.

On divergence: tmpdir, clone --bare from ourselves (localhost is
cheap, an empty mirror on first run is fine), fetch +heads/* +tags/*
from github (delta only), push --mirror back to ourselves, rm.
No persistent cache — the temp dir lives only for one tick.
"""

import os
import shutil
import subprocess
import sys
import tempfile


TARGET = 'http://127.0.0.1:8035'


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def ls_remote(url):
    out = subprocess.check_output(
        ['git', 'ls-remote', url, 'refs/heads/*', 'refs/tags/*'],
    ).decode()

    return sorted(out.strip().splitlines())


def run(*args):
    subprocess.run(list(args), check=True)


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: ogorod_mirror <repo>')

    name = sys.argv[1]

    src = f'https://github.com/pg83/{name}.git'
    dst = f'{TARGET}/mirror_{name}.git'

    if ls_remote(src) == ls_remote(dst):
        return

    log(f'syncing {name}')

    tmp = tempfile.mkdtemp(prefix='ogorod_mirror_')

    try:
        run('git', 'clone', '--bare', dst, tmp)
        run('git', '--git-dir', tmp, 'fetch', '--prune', src,
            '+refs/heads/*:refs/heads/*', '+refs/tags/*:refs/tags/*')
        run('git', '--git-dir', tmp, 'push', '--mirror', dst)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
