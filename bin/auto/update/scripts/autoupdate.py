#!/usr/bin/env python3

"""
One autoupdate tick:

  1. Sleep briefly so a failing loop doesn't DOS the host.
  2. Log /bin/runpy sha256 — heartbeat into Loki, tells which
     revision each host is running, no SSH needed.
  3. Probe github via ls-remote (one round-trip). If HEAD matches
     the local ix/ checkout, stop — no work to do.
  4. Stage the upgrade in ix1/: copy current ix/ aside, pull there,
     run `ix mut system` + `ix mut $(ix list)` against the staged
     tree. On any failure: leave ix/ at the previous (deployed)
     ref so the next cycle tries again. Without staging, a failed
     mutation would leave ix/ at the new ref, the ls-remote probe
     would now match, and the cycle would think "nothing to do" —
     a transient network blip permanently leaving us un-built.
  5. On success: atomic swap ix/ ← ix1/.

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
NEW = 'ix1'


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


def remote_head(url):
    return run('git', 'ls-remote', '--quiet', url, 'HEAD', capture=True).stdout.split()[0]


def local_head(dst):
    return run('git', 'rev-parse', 'HEAD', cwd=dst, capture=True).stdout.strip()


def build(checkout):
    # Use staged tree's own ./ix; /bin/ix is pinned to DST.
    ix = os.path.abspath(os.path.join(checkout, 'ix'))

    run(ix, 'mut', 'system')

    pkgs = run(ix, 'list', capture=True).stdout.split()

    run(ix, 'mut', *pkgs)


def main():
    time.sleep(10)

    log(f'autoupdate_ix: runpy-sha256={runpy_sha()}')

    # First-time bootstrap: clone straight into DST.
    if not os.path.isdir(os.path.join(DST, '.git')):
        clone(URL, DST)
        build(DST)

        return

    if remote_head(URL) == local_head(DST):
        return

    # Stage upgrade so a failed build doesn't move DST forward.
    if os.path.exists(NEW):
        shutil.rmtree(NEW)

    # cp -a preserves symlinks/perms; submodules + .git/ come along.
    run('cp', '-a', DST, NEW)

    try:
        run('git', 'pull', cwd=NEW)
        run('git', 'submodule', 'update', '--init', '--recursive', cwd=NEW)
        build(NEW)
    except subprocess.CalledProcessError:
        log('staged build failed; leaving ix at previous ref, retry next cycle')
        shutil.rmtree(NEW)

        raise

    log(f'staged build succeeded; promoting {NEW} → {DST}')

    backup = DST + '.bak'

    if os.path.exists(backup):
        shutil.rmtree(backup)

    os.rename(DST, backup)
    os.rename(NEW, DST)
    shutil.rmtree(backup)


if __name__ == '__main__':
    main()
