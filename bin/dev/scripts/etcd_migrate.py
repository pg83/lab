#!/usr/bin/env python3

"""
Dump / restore etcd keyspace as jsonlines.

Used to migrate `etcd_private` (peer URLs on nebula, client on lab*.nebula:8020)
to `etcd_1` (peer URLs on gofra, client on 127.0.0.1:8020) by:

    # 1. dump live keys from old cluster
    etcd_migrate dump --endpoints lab1.nebula:8020,lab2.nebula:8020,lab3.nebula:8020 > snap.jsonl

    # 2. roll out config: etcd_private → DISABLE_ALL, etcd_1 starts fresh

    # 3. restore into new cluster
    etcd_migrate restore --endpoints 127.0.0.1:8020 < snap.jsonl

jsonl record (one per line):

    {"k": "<base64 key bytes>", "v": "<base64 value bytes>"}

Keys/values are base64'd because etcd accepts arbitrary bytes — gorn task
queue holds pickle blobs, /ogorod/version/* is a raw int. Lease info is
not preserved: the only TTL'd keys we have are mutex locks, which the
holders recreate.
"""

import argparse
import base64
import json
import os
import subprocess
import sys


def log(*a):
    print('+', *a, file=sys.stderr, flush=True)


def endpoints_arg(parser):
    parser.add_argument(
        '--endpoints',
        default=os.environ.get('ETCDCTL_ENDPOINTS', ''),
        help='comma-separated etcd endpoints; falls back to ETCDCTL_ENDPOINTS',
    )


def etcdctl(endpoints, *args, input_bytes=None, capture=False):
    if not endpoints:
        raise SystemExit('endpoints not set (pass --endpoints or set ETCDCTL_ENDPOINTS)')

    env = os.environ.copy()
    env.pop('ETCDCTL_ENDPOINTS', None)
    cmd = ['etcdctl', '--endpoints', endpoints, '--command-timeout=30s', *args]

    return subprocess.run(
        cmd,
        env=env,
        input=input_bytes,
        check=True,
        stdout=subprocess.PIPE if capture else None,
    )


def cmd_dump(args):
    res = etcdctl(args.endpoints, 'get', '--prefix', '', '-w', 'json', capture=True)
    payload = json.loads(res.stdout)
    kvs = payload.get('kvs') or []

    log(f'dumping {len(kvs)} keys')

    for kv in kvs:
        k = kv['key']
        v = kv.get('value', '')
        rec = {'k': k, 'v': v}
        sys.stdout.write(json.dumps(rec, separators=(',', ':')) + '\n')

    sys.stdout.flush()
    log('dump done')


def cmd_restore(args):
    n = 0

    for line in sys.stdin:
        line = line.strip()

        if not line:
            continue

        rec = json.loads(line)
        key = base64.b64decode(rec['k'])
        val = base64.b64decode(rec['v'])

        if args.dry_run:
            log(f'would put {key!r} ({len(val)} bytes)')
        else:
            etcdctl(args.endpoints, 'put', '--', key.decode('utf-8'), input_bytes=val)

        n += 1

    log(f'{"would restore" if args.dry_run else "restored"} {n} keys')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    pd = sub.add_parser('dump', help='dump every key under prefix "" to stdout as jsonl')
    endpoints_arg(pd)
    pd.set_defaults(func=cmd_dump)

    pr = sub.add_parser('restore', help='read jsonl from stdin and put into etcd')
    endpoints_arg(pr)
    pr.add_argument('--dry-run', action='store_true', help='print what would be written, do not call put')
    pr.set_defaults(func=cmd_restore)

    args = p.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
