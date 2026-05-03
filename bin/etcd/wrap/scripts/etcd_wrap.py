#!/usr/bin/env python3

"""
etcd_wrap: ephemeral-etcd wrapper with tar.zstd backup to MinIO.

Goal: data_dir lives on tmpfs for performance; tar.zstd of data_dir
lives in MinIO, so a member can rejoin after a host reboot without
the member-remove/member-add ceremony — member_id, raft state and
cluster_id are byte-preserved, leader catches us up with whatever raft
entries accumulated since the last backup via standard replication.

Flow:
  1. Random sleep [0, jitter] to stagger restarts across the cluster.
  2. If data_dir is empty:
       - mc cp <backup-uri> ./restore.tar.zstd. Failed (no backup yet,
         or transient minio error) -> log and exit 0; runit will retry.
         Genesis is an admin operation: seed the first backup once.
       - tar+zstd extract into data_dir. Failed -> rename archive to
         .broken and exit 0; we won't try empty-start with cluster_state
         that doesn't exist in our config anyway.
  3. exec etcd as child with signal.alarm(timeout) -> SIGTERM. Forward
     SIGTERM/SIGINT/SIGHUP from runit so graceful shutdown propagates.
  4. After etcd exits, if data_dir is non-empty: tar+zstd, mc cp back
     to the same uri. Atomic at S3 level (multipart-upload completes
     atomically).
  5. exit; runit re-runs us.
"""

import argparse
import os
import random
import signal
import subprocess
import sys
import time


def log(*args):
    print('etcd_wrap:', *args, file=sys.stderr, flush=True)


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True)
    ap.add_argument('--backup-uri', required=True,
                    help='mc-alias-prefixed path, e.g. minio/etcd/3/lab1.tar.zstd')
    ap.add_argument('--timeout', type=int, required=True,
                    help='SIGTERM the child after N seconds')
    ap.add_argument('--jitter', type=int, required=True,
                    help='random sleep [0, jitter] on start')
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


def mc(*args, check=True, capture=False):
    log('minio-client', *args)

    return subprocess.run(
        ('minio-client',) + args,
        check=check,
        stdout=subprocess.PIPE if capture else None,
        text=True if capture else None,
    )


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
    if not have_data(data_dir):
        log('data_dir empty after etcd run; skip backup')

        return

    tmp_archive = './backup.tar.zstd'

    try:
        tar_create_zstd(data_dir, tmp_archive)
        mc('cp', tmp_archive, backup_uri)
        log(f'backup uploaded to {backup_uri}')
    finally:
        if os.path.exists(tmp_archive):
            os.unlink(tmp_archive)


def run_etcd(argv, timeout):
    log('exec', *argv)

    proc = subprocess.Popen(argv)

    def alarm_handler(_signo, _frame):
        log(f'timeout {timeout}s reached; SIGTERM etcd pid={proc.pid}')

        try:
            proc.terminate()
        except ProcessLookupError:
            pass

    def fwd_handler(signo, _frame):
        log(f'forwarding signal {signo} to etcd pid={proc.pid}')

        try:
            proc.send_signal(signo)
        except ProcessLookupError:
            pass

    signal.signal(signal.SIGALRM, alarm_handler)
    signal.signal(signal.SIGTERM, fwd_handler)
    signal.signal(signal.SIGINT, fwd_handler)
    signal.signal(signal.SIGHUP, fwd_handler)

    signal.alarm(timeout)

    rc = proc.wait()
    signal.alarm(0)
    log(f'etcd exited rc={rc}')

    return rc


def main():
    args = parse()

    sleep_for = random.randint(0, args.jitter)
    log(f'stagger sleep {sleep_for}s of jitter {args.jitter}s')
    time.sleep(sleep_for)

    if not have_data(args.data_dir):
        log(f'data_dir {args.data_dir} empty; restoring from {args.backup_uri}')

        if not restore(args.data_dir, args.backup_uri):
            sys.exit(0)

    rc = run_etcd(args.etcd_argv, args.timeout)

    backup(args.data_dir, args.backup_uri)

    sys.exit(rc)


if __name__ == '__main__':
    main()
