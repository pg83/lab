#!/usr/bin/env python3

"""Queue a Quay upload for each new CAS content SHA."""

import json
import os
import subprocess
import sys


def main():
    sha = json.load(sys.stdin)['payload']['sha']

    print(f'+ quay_push_event: gorn ignite quay_sync sha={sha}', file=sys.stderr, flush=True)

    subprocess.run(
        (
            'gorn', 'ignite',
            '--api', os.environ['GORN_API'],
            '--root', 'quay_sync',
            '--guid', f'quay_push_{sha}',
            '--retry-error', '1',
            '--env', f'MC_HOST_minio={os.environ["MC_HOST_minio_cas"]}',
            '--env', f'QUAY_TOKEN={os.environ["QUAY_TOKEN"]}',
            '--',
            '/bin/env', 'PATH=/bin',
            'quay_push_one', sha,
        ),
        check=True,
    )


if __name__ == '__main__':
    main()
