#!/usr/bin/env python3

"""
hf_push_event — subscriber to kind=new_sha events. Reads
{"kind":"new_sha","guid":"...","payload":{"sha":"<content-sha>"}}
on stdin and fires `gorn ignite --root hf_sync --
hf_push_one <sha>` (async). The worker downloads minio/cas/<sha>
and uploads it as cas/<aa>/<sha> on the stal-ix/pkgsrc HF dataset.
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
    sha = payload.get('sha')

    if not sha:
        print(f'hf_push_event: missing sha in payload {payload}', file=sys.stderr)
        sys.exit(2)

    log(f'hf_push_event: gorn ignite hf_sync sha={sha}')

    subprocess.run(
        (
            'gorn', 'ignite',
            '--api', os.environ['GORN_API'],
            '--root', 'hf_sync',
            '--guid', f'hf_push_{sha}',
            '--env', f'GORN_API={os.environ["GORN_API"]}',
            '--env', f'S3_ENDPOINT={os.environ["S3_ENDPOINT"]}',
            '--env', f'AWS_ACCESS_KEY_ID={os.environ["AWS_ACCESS_KEY_ID_CAS"]}',
            '--env', f'AWS_SECRET_ACCESS_KEY={os.environ["AWS_SECRET_ACCESS_KEY_CAS"]}',
            '--env', f'HF_TOKEN={os.environ["HF_TOKEN"]}',
            '--',
            '/bin/env', 'PATH=/bin',
            'hf_push_one', sha,
        ),
        check=True,
    )


if __name__ == '__main__':
    main()
