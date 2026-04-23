#!/usr/bin/env python3

"""
job_scheduler — cluster cron.

Reads /etc/cron/<delay>-<name>.json every 10 seconds. Each file names
a job that should run no more often than <delay> seconds. Example:

    /etc/cron/100-ci.json
        {"cmd": ["gorn", "ignite", "--env", "A=$B", ...]}

$VAR / ${VAR} in cmd args are expanded from job_scheduler's own
environment — which means the service runs with every secret any
scheduled command might need (S3, gorn API, etcd endpoints). That's
a deliberate tradeoff for keeping the scheduler itself trivial.

Each tick:

  - seed `state[filename] = now - random(0, delay)` on first sight of
    a filename — spreads initial fires across one delay window instead
    of stampeding on startup
  - if state[filename] + delay > now: skip
  - else: run `timeout 10s <expanded-cmd>`, inheriting stdout/stderr
    into our log. Exit 0 → state[filename] = now. Non-zero → leave
    state alone, next tick retries.

Designed to run under `etcdctl lock /lock/job/scheduler` across 3
hosts so only the lock-holder actually fires jobs; peers block inside
etcdctl until the holder dies.
"""

import json
import os
import random
import subprocess
import sys
import time


CRON_DIR = '/etc/cron'
POLL_INTERVAL_S = 10
JOB_TIMEOUT = '10s'


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def parse_delay(fn):
    # '100-ci.json' → 100. Fail-loud on a mis-named file: this is
    # config error, not a runtime blip to swallow.
    head = fn.split('-', 1)[0]
    return int(head)


def expand(cmd):
    return [os.path.expandvars(a) for a in cmd]


def tick(state):
    now = time.time()

    try:
        entries = sorted(os.listdir(CRON_DIR))
    except FileNotFoundError:
        return

    for fn in entries:
        if not fn.endswith('.json'):
            continue

        delay = parse_delay(fn)

        # First sight: seed randomly in [now-delay, now] so the first
        # fire falls somewhere in [now, now+delay] instead of all
        # files firing together on boot.
        if fn not in state:
            state[fn] = now - random.uniform(0, delay)

        if state[fn] + delay > now:
            continue

        with open(os.path.join(CRON_DIR, fn)) as f:
            cfg = json.load(f)

        cmd = ['timeout', JOB_TIMEOUT] + expand(cfg['cmd'])
        log(f'run {fn}: {cmd}')

        res = subprocess.run(cmd, check=False)

        if res.returncode == 0:
            state[fn] = now
        else:
            log(f'{fn}: exit {res.returncode}, will retry next tick')


def main():
    state = {}

    while True:
        tick(state)
        time.sleep(POLL_INTERVAL_S)


if __name__ == '__main__':
    main()
