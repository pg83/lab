#!/usr/bin/env python3

"""
ghcr_push_event — subscriber to kind=new_sha events. Reads
{"kind":"new_sha","guid":"...","payload":{"sha":"<content-sha>"}}
on stdin and fires `gorn ignite --root ghcr_sync --
ghcr_push_one <sha>` (async). The worker downloads minio/cas/<sha>
and oras-pushes it to ghcr.io/stal-ix/pkgsrc/<a>:<sha>.
"""

import json
import os
import subprocess
import sys


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def main():
    req = json.load(sys.stdin)
    payload = req['payload']
    sha = payload['sha']

    log(f'ghcr_push_event: gorn ignite ghcr_sync sha={sha}')

    subprocess.run(
        (
            'gorn', 'ignite',
            '--api', os.environ['GORN_API'],
            '--root', 'ghcr_sync',
            '--guid', f'ghcr_push_{sha}',
            '--env', f'GORN_API={os.environ["GORN_API"]}',
            '--env', f'S3_ENDPOINT={os.environ["S3_ENDPOINT"]}',
            '--env', f'AWS_ACCESS_KEY_ID={os.environ["AWS_ACCESS_KEY_ID_CAS"]}',
            '--env', f'AWS_SECRET_ACCESS_KEY={os.environ["AWS_SECRET_ACCESS_KEY_CAS"]}',
            '--env', f'GHCR_TOKEN={os.environ["GHCR_TOKEN"]}',
            '--',
            '/bin/env', 'PATH=/bin',
            'ghcr_push_one', sha,
        ),
        check=True,
    )


if __name__ == '__main__':
    main()
