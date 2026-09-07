#!/usr/bin/env python3

"""Rebuild s3://molot/complete from the result objects in MinIO.

Each line is "uid <md5>": the recursive listing hands us every
result.zstd ETag for free, and single-part uploads make ETag == MD5,
which molot cache serves via /v2/resolve for client-side blob
verification.  Objects without a usable ETag land as a bare uid."""

import json
import os
import subprocess
import tempfile
import time


SOURCE = 'minio/molot/molot/'
DESTINATION = 'minio/molot/complete'


def copy_uids(lines, out):
    count = 0

    for line in lines:
        record = json.loads(line)

        if record.get('status') != 'success':
            raise RuntimeError(f'unexpected minio ls record: {record!r}')

        if record.get('type') != 'file':
            continue

        key = record.get('key', '')
        parts = key.split('/')

        if len(parts) != 2 or parts[1] != 'result.zstd':
            continue

        uid = parts[0]

        if not uid or '\\' in uid:
            raise RuntimeError(f'invalid result key: {key!r}')

        etag = record.get('etag', '').strip('"')

        if etag and '-' not in etag:
            out.write(f'{uid} {etag}\n')
        else:
            out.write(uid + '\n')

        count += 1

    return count


def main():
    if not os.environ.get('MC_HOST_minio'):
        raise SystemExit('MC_HOST_minio is required')

    started = time.monotonic()
    fd, path = tempfile.mkstemp(prefix='molot-complete.', dir=os.getcwd(), text=True)

    try:
        with os.fdopen(fd, 'w') as out:
            proc = subprocess.Popen(
                ('minio-client', 'ls', '--json', '--recursive', SOURCE),
                stdout=subprocess.PIPE,
                text=True,
            )

            try:
                count = copy_uids(proc.stdout, out)
            except BaseException:
                proc.kill()
                proc.wait()
                raise

            if proc.wait() != 0:
                raise subprocess.CalledProcessError(proc.returncode, proc.args)

        subprocess.run(
            ('minio-client', 'cp', path, DESTINATION),
            check=True,
        )
    finally:
        if os.path.exists(path):
            os.remove(path)

    elapsed = time.monotonic() - started
    print(f'molot complete: wrote {count} uids in {elapsed:.2f}s')


if __name__ == '__main__':
    main()
