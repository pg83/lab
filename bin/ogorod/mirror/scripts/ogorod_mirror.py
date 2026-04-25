#!/usr/bin/env python3

"""
Mirror github.com/pg83/<r> → http://127.0.0.1:8035/mirror_<r>.git
under /lock/ogorod/mirror/<r>, fired every 10s by job_scheduler.
The repo name is the only argv: the cron generator emits one entry
per repo so each sync runs on its own lock.

ls-remote both upstream and our mirror, sort, compare. Equality
(the common case) means an early return — the whole tick is two
cheap HTTPS round-trips and no I/O.

On divergence: clone --bare on first run, fetch +heads/* +tags/*
thereafter, push --mirror to the local ogorod_serve. Cache lives
in /var/run/ogorod_mirror/cache/<r>; survives ticks, wiped on
reboot — first tick post-boot re-clones from upstream.
"""

import os
import subprocess
import sys


TARGET = 'http://127.0.0.1:8035'
CACHE = '/var/run/ogorod_mirror/cache'


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

    cache_dir = f'{CACHE}/{name}'

    os.makedirs(CACHE, exist_ok=True)

    if os.path.isdir(cache_dir):
        log(f'fetching {name}')
        run('git', '--git-dir', cache_dir, 'fetch', '--prune', 'origin',
            '+refs/heads/*:refs/heads/*', '+refs/tags/*:refs/tags/*')
    else:
        log(f'cloning {name}')
        run('git', 'clone', '--bare', src, cache_dir)

    log(f'pushing {name} -> mirror_{name}')
    run('git', '--git-dir', cache_dir, 'push', '--mirror', dst)


if __name__ == '__main__':
    main()
