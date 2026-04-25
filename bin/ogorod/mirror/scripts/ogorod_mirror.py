#!/usr/bin/env python3

"""
Mirror github.com/pg83/<r> → http://127.0.0.1:8035/mirror_<r>.git
under /lock/ogorod/mirror/<r>, fired every 10s by job_scheduler.
The repo name is the only argv: the cron generator emits one entry
per repo so each sync runs on its own lock.

ls-remote both upstream and our mirror, sort, compare. Equality
(the common case) means an early return — the whole tick is two
cheap HTTPS round-trips and no I/O.

On divergence: keep a bare git dir at <cwd>/<r>, init it if first
seen, fetch +heads/* +tags/* from github (delta only after first
run), push --mirror to ourselves. No cleanup; state persists in
the scheduler's cwd between ticks so only deltas move on the wire.
"""

import os
import subprocess
import sys


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

    bare = os.path.abspath(name)

    if not os.path.exists(os.path.join(bare, 'HEAD')):
        run('git', 'init', '--bare', bare)

    run('git', '--git-dir', bare, 'fetch', '--prune', src,
        '+refs/heads/*:refs/heads/*', '+refs/tags/*:refs/tags/*')

    run('git', '--git-dir', bare, 'push', '--mirror', dst)


if __name__ == '__main__':
    main()
