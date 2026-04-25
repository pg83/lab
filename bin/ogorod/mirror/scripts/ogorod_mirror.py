#!/usr/bin/env python3

"""
Mirror github.com/pg83/<r> → http://127.0.0.1:8035/mirror_<r>.git
under /lock/ogorod/mirror/<r>, fired every 10s by job_scheduler
and shipped to a gorn worker via `gorn ignite`. The repo name is
the only argv; the cron generator emits one entry per repo so each
sync runs on its own lock and on whichever worker is free.

ls-remote both upstream and our mirror, sort, compare. Equality
(the common case) means an early return — the whole tick is two
cheap HTTPS round-trips and no I/O.

On divergence: gorn-wrap put us in a fresh tmpfs ns, so cwd is
empty. clone --bare from ourselves (localhost is cheap; an empty
mirror on first run is fine), fetch +heads/* +tags/* from github
(delta only thanks to clone-from-self seeding the have-state),
push --mirror back to us.

clone-from-self can fail when our mirror is in a corrupt or
half-wiped state (lost packs, stale packed-refs, etc). In that
case fall back to `git init --bare` and let push --mirror replace
our state from scratch. Without this fallback any corruption is
permanent — every cron tick ls-remote sees a stale ref, decides
to sync, and the clone re-trips the same broken state.

Sleep 100s before the init fallback. After init the fetch from
github is no-delta (we have no objects), so the next push is a
full re-pull from upstream. If clone-from-self is failing for an
infra reason that affects all repos (ogorod_serve down, network
flap), every cron tick on every repo on every host would otherwise
fall into the init path and do a full github fetch — that's a
self-inflicted DDoS on upstream. The sleep stretches the cron
period from ~10s to ~110s while clone-from-self is broken, cutting
the load on github by ~10x during incidents.
"""

import os
import subprocess
import sys
import time


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

    try:
        run('git', 'clone', '--bare', dst, '.')
    except subprocess.CalledProcessError:
        log(f'clone-from-self failed for {name}; sleeping 100s before init+fetch to throttle upstream')
        time.sleep(100)
        # Failed clone leaves partial refs in both refs/ and packed-refs;
        # init alone is idempotent and won't clear them, so the upcoming
        # fetch creates loose refs that shadow the packed ones and push
        # --mirror fails with "dst refspec ... matches more than one".
        # Wipe cwd (gorn-wrap tmpfs, fully ours) before init.
        run('find', '.', '-mindepth', '1', '-delete')
        run('git', 'init', '--bare', '.')

    run('git', 'fetch', '--prune', src,
        '+refs/heads/*:refs/heads/*', '+refs/tags/*:refs/tags/*')

    run('git', 'push', '--mirror', dst)


if __name__ == '__main__':
    main()
