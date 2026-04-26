#!/usr/bin/env python3

"""
One-shot bootstrap for nebula-ng PKI: generate a CA + per-host certs
for lab1/lab2/lab3 and push the resulting material to etcd under
/nebula/ng/{ca.crt,labN.crt,labN.key}.

Run once from any lab host (etcdctl + nebula-cert in PATH from the
package run_deps). Idempotent — bails if /nebula/ng/ca.crt already
holds material; pass --force to overwrite (requires restarting every
deployed nebula-ng instance afterwards, since the CA changes).

Subnet is hardcoded to 192.168.101.0/24 with VIPs:
  lab1 → 192.168.101.16
  lab2 → 192.168.101.17
  lab3 → 192.168.101.18

We deliberately do NOT push the CA private key to etcd. Adding hosts
later means re-running this script with --force, which regenerates
everything.
"""

import os
import subprocess
import sys
import tempfile


HOSTS = [
    ('lab1', '192.168.101.16/24'),
    ('lab2', '192.168.101.17/24'),
    ('lab3', '192.168.101.18/24'),
]
ETCD_PREFIX = '/nebula/ng'
CA_NAME = 'lab-ng'
DURATION = '50000h'


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def etcdctl_get(key):
    return subprocess.run(
        ['etcdctl', 'get', '--print-value-only', key],
        check=True, capture_output=True,
    ).stdout


def etcdctl_put(key, value_path):
    with open(value_path, 'rb') as f:
        data = f.read()

    subprocess.run(['etcdctl', 'put', key], check=True, input=data)
    log(f'put {key} ({len(data)} bytes)')


def main():
    force = '--force' in sys.argv[1:]

    existing = etcdctl_get(f'{ETCD_PREFIX}/ca.crt')

    if existing and not force:
        print(
            f'{ETCD_PREFIX}/ca.crt already holds {len(existing)} bytes; '
            f'pass --force to overwrite (will require restarting every '
            f'nebula-ng instance)',
            file=sys.stderr,
        )
        sys.exit(1)

    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        log(f'workdir {d}')

        subprocess.run(
            ['nebula-cert', 'ca', '-name', CA_NAME, '-duration', DURATION],
            check=True,
        )
        log('generated ca.crt + ca.key')

        for name, ip in HOSTS:
            subprocess.run(
                ['nebula-cert', 'sign',
                 '-ca-crt', 'ca.crt', '-ca-key', 'ca.key',
                 '-name', name, '-ip', ip, '-duration', DURATION],
                check=True,
            )
            log(f'signed {name} {ip}')

        etcdctl_put(f'{ETCD_PREFIX}/ca.crt', 'ca.crt')

        for name, _ in HOSTS:
            etcdctl_put(f'{ETCD_PREFIX}/{name}.crt', f'{name}.crt')
            etcdctl_put(f'{ETCD_PREFIX}/{name}.key', f'{name}.key')

    log(f'done — pushed CA + {len(HOSTS)} host certs under {ETCD_PREFIX}')


if __name__ == '__main__':
    main()
