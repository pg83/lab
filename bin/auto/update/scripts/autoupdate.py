#!/usr/bin/env python3

"""
One autoupdate tick:

  1. Sleep briefly so a failing loop doesn't DOS the host.
  2. Log current /bin/runpy sha256 — a heartbeat that tells Loki
     which revision each host is running right now, answerable
     without SSH.
  3. Probe github for new commits via ls-remote (cheap, single
     round-trip). If HEAD matches local, stop — no work to do.
  4. Pull. On any pull failure, wipe and re-clone.
  5. ix mut system, then ix mut $(ix list).

Runit re-execs us on exit; the sleep at step 1 is the rate limit.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import time


URL = 'https://github.com/pg83/lab'
DST = 'ix'


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def run(*args, cwd=None, capture=False):
    log(*args, f'(cwd={cwd})' if cwd else '')
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE if capture else None,
        text=True if capture else None,
    )


def runpy_sha():
    with open('/bin/runpy', 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def clone(url, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)

    run('git', 'clone', '--recurse-submodules', url, dst)


def has_new_commits(url, dst):
    # Fresh / corrupted checkout → treat as "definitely new".
    if not os.path.isdir(os.path.join(dst, '.git')):
        clone(url, dst)

        return True

    # ls-remote is one TCP round-trip returning ~1 KB; designed for
    # frequent polling. A full `git pull` negotiates upload-pack
    # every time regardless of whether anything changed, which on a
    # 10s cycle × 12+ services hits GitHub's abuse rate-limiter.
    remote = run('git', 'ls-remote', '--quiet', url, 'HEAD', capture=True).stdout.split()[0]
    local = run('git', 'rev-parse', 'HEAD', cwd=dst, capture=True).stdout.strip()

    if remote == local:
        return False

    try:
        run('git', 'pull', cwd=dst)
    except subprocess.CalledProcessError:
        log('pull failed — wiping and re-cloning')
        clone(url, dst)

        return True

    run('git', 'submodule', 'update', '--init', '--recursive', cwd=dst)

    return True


def main():
    time.sleep(10)

    log(f'autoupdate_ix: runpy-sha256={runpy_sha()}')

    if not has_new_commits(URL, DST):
        return

    run('ix', 'mut', 'system')
    pkgs = run('ix', 'list', capture=True).stdout.split()
    run('ix', 'mut', *pkgs)


if __name__ == '__main__':
    main()
