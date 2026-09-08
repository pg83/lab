#!/usr/bin/env python3

"""Remove artifacts unused for 30 days and rebuild s3://molot/complete.

Use the last request recorded in stats, or the result object's modification
time when the uid has no stats entry. Delete the entire expired uid prefix.

Each line is "uid <md5>": the recursive listing hands us every
result.zstd ETag for free, and single-part uploads make ETag == MD5,
which molot cache serves via /v2/resolve for client-side blob
verification.  Objects without a usable ETag land as a bare uid."""

from datetime import datetime
import json
import os
import subprocess
import tempfile
import time


SOURCE = 'minio/molot/molot/'
DESTINATION = 'minio/molot/complete'
STATS = 'minio/molot/stats'
RETENTION = 30 * 24 * 60 * 60


def copy_uids(lines, out, stats, cutoff):
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

        if not uid or uid in ('.', '..') or '\\' in uid:
            raise RuntimeError(f'invalid result key: {key!r}')

        last_used = stats.get(uid)

        if last_used is None:
            modified = datetime.fromisoformat(record['lastModified'].replace('Z', '+00:00'))

            if modified.tzinfo is None:
                raise ValueError(f'missing timezone in lastModified: {key!r}')

            last_used = modified.timestamp()

        if last_used < cutoff:
            subprocess.run(
                ('minio-client', 'rm', '--recursive', '--force', SOURCE + uid + '/'),
                check=True,
            )
            print(f'molot complete: removed {uid}')
            continue

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
    stats = json.loads(subprocess.check_output(('minio-client', 'cat', STATS), text=True))

    if not isinstance(stats, dict) or any(type(ts) is not int for ts in stats.values()):
        raise ValueError('invalid molot stats: expected UID -> unix timestamp')

    cutoff = time.time() - RETENTION
    fd, path = tempfile.mkstemp(prefix='molot-complete.', dir=os.getcwd(), text=True)

    try:
        with os.fdopen(fd, 'w') as out:
            proc = subprocess.Popen(
                ('minio-client', 'ls', '--json', '--recursive', SOURCE),
                stdout=subprocess.PIPE,
                text=True,
            )

            try:
                count = copy_uids(proc.stdout, out, stats, cutoff)
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
