#!/usr/bin/env python3

"""
Walk ETCDCTL_ENDPOINTS one endpoint at a time and `etcdctl defrag`
each. Run under gorn ignite via the bin/etcd/defrag cron — one
gorn task handles the whole cluster sequentially, no per-host
coordination needed (defrag of one endpoint doesn't block the
others; the other two keep serving during each defrag).

--command-timeout=5m matters: the etcdctl default 5s kills on
multi-GiB backend files long before defrag finishes its bbolt
compaction pass.
"""

import os
import subprocess
import sys
import time


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def main():
    endpoints = [e.strip() for e in os.environ.get('ETCDCTL_ENDPOINTS', '').split(',') if e.strip()]

    if not endpoints:
        raise SystemExit('ETCDCTL_ENDPOINTS empty')

    # Wipe ETCDCTL_ENDPOINTS out of the child env before each defrag.
    # Keeping it alongside --endpoints is ambiguous across etcdctl
    # versions (flag-vs-env precedence) and can fan the defrag out
    # to the whole cluster at once instead of doing it one-by-one.
    env = os.environ.copy()
    env.pop('ETCDCTL_ENDPOINTS', None)

    for ep in endpoints:
        t0 = time.time()
        log(f'defrag {ep}')
        subprocess.run(
            ['etcdctl', '--endpoints', ep, '--command-timeout=5m', 'defrag'],
            env=env,
            check=True,
        )
        log(f'defrag {ep} done in {time.time() - t0:.1f}s')


if __name__ == '__main__':
    main()
