#!/usr/bin/env python3

"""Queue a ModelScope upload for each new CAS content SHA."""

import json
import os
import subprocess
import sys


def main():
    sha = json.load(sys.stdin)['payload']['sha']

    print(f'+ modelscope_push_event: gorn ignite modelscope_sync sha={sha}', file=sys.stderr, flush=True)

    result = subprocess.run(
        (
            'gorn', 'ignite',
            '--api', os.environ['GORN_API'],
            '--root', 'modelscope_sync',
            '--guid', f'modelscope_push_{sha}',
            '--retry-error', '1',
            '--env', f'MC_HOST_minio={os.environ["MC_HOST_minio_cas"]}',
            '--env', f'MODELSCOPE_TOKEN={os.environ["MODELSCOPE_TOKEN"]}',
            '--',
            '/bin/env', 'PATH=/bin',
            'modelscope_push_one', sha,
        ),
        check=False,
    )
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
