#!/usr/bin/env python3

"""
gpull URL DIR

Fast-forward DIR from URL (with submodules) and communicate via exit
code whether the working tree moved:

  exit 0   → new commits pulled (or fresh clone). Caller rebuilds.
  exit 7   → already up-to-date, nothing to do.
  exit !=0 → hard failure (clone died, network dead, etc.).

Callers under `set -e` naturally short-circuit on 7 — exactly what
autoupdate_cycle / ci_cycle want: a cheap "nothing new, wait for next
runit restart" signal without any change on their side.
"""

import os
import shutil
import subprocess
import sys


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def git(*args, cwd=None):
    log('git', *args, f'(cwd={cwd})' if cwd is not None else '')
    # stderr left unredirected so real git diagnostics (auth prompts,
    # network errors, merge conflicts) surface in the service log.
    subprocess.run(('git',) + args, cwd=cwd, check=True)


def git_rev_parse_head(cwd):
    log('git', 'rev-parse', 'HEAD', f'(cwd={cwd})')
    res = subprocess.run(
        ('git', 'rev-parse', 'HEAD'),
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )

    return res.stdout.strip()


def clone(url, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)

    git('clone', '--recurse-submodules', url, dst)


def main():
    if len(sys.argv) != 3:
        print('usage: gpull URL DIR', file=sys.stderr)
        sys.exit(2)

    url, dst = sys.argv[1], sys.argv[2]

    # Fresh / corrupted checkout → full clone, definitionally "gained
    # new commits".
    if not os.path.isdir(os.path.join(dst, '.git')):
        clone(url, dst)
        sys.exit(0)

    # Cheap probe: ls-remote is a single TCP round-trip returning
    # ~1 KB of ref info — designed for frequent polling. Full
    # `git pull` does a complete upload-pack negotiation every time
    # regardless of whether anything changed, which on a 10s cycle
    # across 12+ services puts us into GitHub abuse-rate-limit
    # territory (~1 req/sec per IP). ls-remote keeps us well below.
    log('git', 'ls-remote', '--quiet', url, 'HEAD')
    remote_head = subprocess.run(
        ('git', 'ls-remote', '--quiet', url, 'HEAD'),
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.split()[0]

    local_head = git_rev_parse_head(dst)

    if remote_head == local_head:
        sys.exit(7)

    # Actual new commit(s) — do full pull. On failure (history
    # rewrite, detached HEAD, submodule config drift, …) wipe and
    # re-clone as coarse recovery; a successful re-clone also counts
    # as "gained new commits".
    try:
        git('pull', cwd=dst)
    except subprocess.CalledProcessError:
        log('pull failed — wiping and re-cloning')
        clone(url, dst)
        sys.exit(0)

    git('submodule', 'update', '--init', '--recursive', cwd=dst)

    sys.exit(0)


if __name__ == '__main__':
    main()
