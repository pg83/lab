#!/usr/bin/env python3

"""
Snapshot the primary etcd cluster, zstd-compress, upload to MinIO
under Tower-of-Hanoi exponential retention.

Slot K is overwritten every 2^(K+1) hours, so snapshots live:

    slot-00  up to 2h old
    slot-01  up to 4h old
    slot-02  up to 8h old
    ...
    slot-15  up to 65536h (~7.5 years) old

Stateless — slot is chosen purely from wall clock: count of trailing
zero bits in `floor(unix_epoch / 3600)`. No GC; the same 16 keys get
overwritten forever.

Invoked on a gorn worker via `gorn ignite -- etcd_backup`; fired
every hour by job_scheduler under /lock/backup/etcd + dedup.
cwd is a fresh tmpfs inside the gorn wrap ns.
"""

import os
import subprocess
import sys
import time


SLOT_CAP = 15
CREDS_REQUIRED = (
    'AWS_ACCESS_KEY_ID',
    'AWS_SECRET_ACCESS_KEY',
    'S3_ENDPOINT',
    'ETCDCTL_ENDPOINTS',
)


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def trailing_zeros(n, cap):
    k = 0

    while n > 0 and n % 2 == 0 and k < cap:
        n //= 2
        k += 1

    return k


def mc_env(base):
    scheme, host = base['S3_ENDPOINT'].split('://', 1)
    env = dict(base)
    env['MC_HOST_etcd'] = f"{scheme}://{base['AWS_ACCESS_KEY_ID']}:{base['AWS_SECRET_ACCESS_KEY']}@{host}"
    return env


def main():
    for k in CREDS_REQUIRED:
        if not os.environ.get(k):
            raise SystemExit(f'{k} not set')

    fire = int(time.time()) // 3600
    slot = trailing_zeros(fire, SLOT_CAP)
    blob = f'slot-{slot:02d}.db.zst'
    snap = 'snap.db'

    subprocess.run(['etcdctl', 'snapshot', 'save', snap], check=True)
    subprocess.run(['zstd', '-10', '-q', '--rm', snap, '-o', blob], check=True)

    key = f'etcd/etcd/backup/{blob}'
    subprocess.run(
        ['minio-client', 'cp', blob, key],
        env=mc_env(os.environ),
        check=True,
    )

    log(f'etcd_backup: fire={fire} → {key} ({os.path.getsize(blob)} bytes)')


if __name__ == '__main__':
    main()
