#!/usr/bin/env python3

"""
ci_hook — subscriber to kind=git events. Reads
{"kind":"git","guid":"...","payload":{"repo":"<r>","sha":"<sha>"}}
on stdin. If repo == 'ix', fires three `gorn ignite` tasks for
ci tier 0/1/2 with deterministic guid set-tier-<tier>-<sha> so
re-fires of the same sha dedup for free. Other repos: log and
exit 0.
"""

import json
import os
import subprocess
import sys


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def main():
    req = json.load(sys.stdin)
    payload = req.get('payload') or {}
    repo = payload.get('repo')
    sha = payload.get('sha')

    if repo != 'ix':
        log(f'ci_hook: skipping repo={repo}')
        return

    if not sha:
        print(f'ci_hook: missing sha in payload {payload}', file=sys.stderr)
        sys.exit(2)

    api = os.environ['GORN_API']
    s3 = os.environ['S3_ENDPOINT']
    cix_key = os.environ['AWS_ACCESS_KEY_ID_CIX']
    cix_sec = os.environ['AWS_SECRET_ACCESS_KEY_CIX']
    etcd = os.environ['ETCDCTL_ENDPOINTS']

    for tier in (0, 1, 2):
        log(f'ci_hook: scheduling ci tier={tier} sha={sha}')

        subprocess.run(
            (
                'gorn', 'ignite',
                '--api', api,
                '--root', 'ci',
                '--guid', f'set-tier-{tier}-{sha}',
                '--env', f'GORN_API={api}',
                '--env', f'S3_ENDPOINT={s3}',
                '--env', f'AWS_ACCESS_KEY_ID={cix_key}',
                '--env', f'AWS_SECRET_ACCESS_KEY={cix_sec}',
                '--env', f'ETCDCTL_ENDPOINTS={etcd}',
                '--env', 'MOLOT_QUIET=1',
                '--env', 'MOLOT_FULL_SLOTS=10',
                '--',
                '/bin/env', 'PATH=/bin',
                'ci', 'check', f'set/ci/tier/{tier}', sha,
            ),
            check=True,
        )


if __name__ == '__main__':
    main()
