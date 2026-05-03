#!/usr/bin/env python3

"""
etcd_wrap: ephemeral-etcd wrapper with tar.zstd backup to MinIO.

Goal: data_dir lives on tmpfs for performance; tar.zstd of data_dir
lives in MinIO, so a member can rejoin after a host reboot without
the member-remove/member-add ceremony — member_id, raft state and
cluster_id are byte-preserved, leader catches us up with whatever raft
entries accumulated since the last backup via standard replication.

Flow (linear, no subprocess supervision):
  1. If data_dir is empty:
       - mc cp <backup-uri> ./restore.tar.zstd. Failed (no backup yet
         or transient minio error) -> exit 0; runit will retry.
         Genesis is an admin operation: seed the first backup once.
       - tar+zstd extract into data_dir. Failed -> rename archive to
         .broken and exit 0.
  2. Backup current data_dir to MinIO BEFORE running etcd. The data_dir
     at this moment is the consistent state from the previous iteration's
     graceful shutdown (`timeout` SIGTERM is what etcd handles cleanly),
     or a freshly-restored archive — either way it's a valid checkpoint.
     Doing backup-at-start lets us exec into `timeout` and forget; we
     don't need to come back after etcd exits.
  3. exec `timeout <actual>s etcd ...`. actual = base + random(0, jitter)
     so each host gets a different shutdown deadline (50%-of-base window
     when jitter == base/2) — 3 nodes don't all SIGTERM together.
"""

import argparse
import os
import random
import subprocess
import sys


def log(*args):
    print('etcd_wrap:', *args, file=sys.stderr, flush=True)


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True)
    ap.add_argument('--backup-uri', required=True,
                    help='mc-alias-prefixed path, e.g. minio/etcd/3/lab1.tar.zstd')
    ap.add_argument('--timeout', type=int, required=True,
                    help='base timeout (seconds); actual = base + rand(0, jitter)')
    ap.add_argument('--jitter', type=int, required=True,
                    help='random extra timeout to add to base (seconds)')
    ap.add_argument('etcd_argv', nargs=argparse.REMAINDER,
                    help='-- followed by etcd binary + args')

    args = ap.parse_args()

    if args.etcd_argv and args.etcd_argv[0] == '--':
        args.etcd_argv = args.etcd_argv[1:]

    if not args.etcd_argv:
        ap.error('expected `-- etcd <args...>` after wrapper flags')

    return args


def have_data(data_dir):
    return os.path.isdir(os.path.join(data_dir, 'member'))


def mc(*args, check=True):
    log('minio-client', *args)

    return subprocess.run(('minio-client',) + args, check=check)


def tar_extract_zstd(src, dst):
    log(f'tar+zstd extract {src} -> {dst}')

    p1 = subprocess.Popen(['zstd', '-dc', src], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(['tar', '-xf', '-', '-C', dst], stdin=p1.stdout)
    p1.stdout.close()
    rc2 = p2.wait()
    rc1 = p1.wait()

    if rc1 != 0 or rc2 != 0:
        raise RuntimeError(f'extract failed (zstd rc={rc1}, tar rc={rc2})')


def tar_create_zstd(src, dst):
    log(f'tar+zstd archive {src} -> {dst}')

    tmp = dst + '.tmp'

    with open(tmp, 'wb') as f:
        p1 = subprocess.Popen(['tar', '-cf', '-', '-C', src, '.'], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(['zstd', '-c'], stdin=p1.stdout, stdout=f)
        p1.stdout.close()
        rc2 = p2.wait()
        rc1 = p1.wait()

    if rc1 != 0 or rc2 != 0:
        os.unlink(tmp)
        raise RuntimeError(f'archive failed (tar rc={rc1}, zstd rc={rc2})')

    os.rename(tmp, dst)


def restore(data_dir, backup_uri):
    tmp_archive = './restore.tar.zstd'

    res = mc('cp', backup_uri, tmp_archive, check=False)

    if res.returncode != 0:
        log(f'mc cp from {backup_uri} failed (rc={res.returncode}); '
            'no backup to restore. NOT starting etcd.')

        return False

    os.makedirs(data_dir, exist_ok=True)

    try:
        tar_extract_zstd(tmp_archive, data_dir)
    except Exception as e:
        broken = tmp_archive + '.broken'
        os.rename(tmp_archive, broken)
        log(f'extract failed ({e}); kept archive as {broken}. NOT starting etcd.')

        return False

    os.unlink(tmp_archive)
    log(f'restored data_dir from {backup_uri}')

    return True


def backup(data_dir, backup_uri):
    tmp_archive = './backup.tar.zstd'

    try:
        tar_create_zstd(data_dir, tmp_archive)
        mc('cp', tmp_archive, backup_uri)
        log(f'backup uploaded to {backup_uri}')
    finally:
        if os.path.exists(tmp_archive):
            os.unlink(tmp_archive)


def main():
    args = parse()

    if not have_data(args.data_dir):
        log(f'data_dir {args.data_dir} empty; restoring from {args.backup_uri}')

        if not restore(args.data_dir, args.backup_uri):
            sys.exit(0)

    backup(args.data_dir, args.backup_uri)

    actual = args.timeout + random.randint(0, args.jitter)
    log(f'effective timeout {actual}s (base {args.timeout}s + {actual - args.timeout}s jitter)')

    cmd = ['timeout', f'{actual}s'] + args.etcd_argv
    log('exec', *cmd)
    os.execvp(cmd[0], cmd)


if __name__ == '__main__':
    main()
