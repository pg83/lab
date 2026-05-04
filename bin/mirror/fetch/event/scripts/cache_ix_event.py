#!/usr/bin/env python3

"""
cache_ix_event — subscriber to kind=git events. Reads
{"kind":"git","guid":"...","payload":{"repo":"<r>","sha":"<sha>"}}
on stdin. If repo == 'ix', fires `gorn ignite --root mirror_fetch
-- cache_ix_sources <sha>` (async — gorn returns once the task
is queued). The worker then fetches urls.txt at <sha> from the
local mirror, downloads new URLs into CAS, and emits one
kind=new_sha event per content sha for hf/ghcr subscribers.
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
        log(f'cache_ix_event: skipping repo={repo}')
        return

    if not sha:
        print(f'cache_ix_event: missing sha in payload {payload}', file=sys.stderr)
        sys.exit(2)

    log(f'cache_ix_event: gorn ignite mirror_fetch sha={sha}')

    subprocess.run(
        (
            'gorn', 'ignite',
            '--api', os.environ['GORN_API'],
            '--root', 'mirror_fetch',
            '--guid', f'cache_ix_sources_{sha}',
            '--env', f'GORN_API={os.environ["GORN_API"]}',
            '--env', f'S3_ENDPOINT={os.environ["S3_ENDPOINT"]}',
            '--env', f'MC_HOST_mirror={os.environ["MC_HOST_minio_mirror"]}',
            '--env', f'MC_HOST_minio={os.environ["MC_HOST_minio_cas"]}',
            '--env', f'EVENT_HTTP_PORT={os.environ["EVENT_HTTP_PORT"]}',
            '--',
            '/bin/env', 'PATH=/bin',
            'cache_ix_sources', sha,
        ),
        check=True,
    )


if __name__ == '__main__':
    main()
