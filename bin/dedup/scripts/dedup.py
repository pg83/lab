#!/usr/bin/env python3

"""
dedup <etcd_path> -- <cmd...>

Single-flight helper for fire-and-forget tools that emit a task id
on stdout (primary target: `gorn ignite` without --wait). Reads
<etcd_path> via etcdctl; if it holds a guid of a task still queued
in gorn ($GORN_API), exits 0 without re-firing — the previous
dispatch hasn't drained yet, no point stacking another on top.

Otherwise runs <cmd>, passes its stdout through untouched, and on
success writes the last non-empty stdout line back into <etcd_path>.

Uses gorn's /v1/tasks/<guid>/queued endpoint — pure etcd-existence
check, no S3 fallback, no root needed. dedup only cares about
"queued vs not"; that's all this endpoint answers.

Usage in practice — cron-file `cmd` array, under etcdctl lock so
two schedulers can't race the read-check-write:

    etcdctl lock /lock/ci/tier_0 \\
        dedup /ci/tier_0 -- \\
            gorn ignite --root ci --env AWS_ACCESS_KEY_ID=$... \\
                -- /bin/env PATH=/bin ci check set/ci/tier/0

Exit policy:
  - previous guid still queued → exit 0, skip.
  - no previous / previous not queued → run cmd.
  - gorn API unreachable → propagate the error (non-zero exit)
    so the scheduler retries the next tick instead of silently
    dropping dispatches on cluster hiccups.
"""

import json
import os
import subprocess
import sys
import urllib.request


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def etcd_get(path):
    res = subprocess.run(
        ('etcdctl', 'get', '--print-value-only', path),
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return res.stdout.strip()


def etcd_put(path, value):
    subprocess.run(('etcdctl', 'put', path, value), check=True)


def gorn_queued(guid):
    api = os.environ['GORN_API'].rstrip('/')
    url = f'{api}/v1/tasks/{guid}/queued'

    with urllib.request.urlopen(url, timeout=10) as resp:
        body = resp.read()

    return bool(json.loads(body).get('queued'))


def main():
    if len(sys.argv) < 4 or sys.argv[2] != '--':
        print('usage: dedup <etcd_path> -- <cmd...>', file=sys.stderr)
        sys.exit(2)

    path = sys.argv[1]
    cmd = sys.argv[3:]

    prev = etcd_get(path)

    if prev:
        if gorn_queued(prev):
            log(f'{path}: {prev} still queued, skipping')
            sys.exit(0)

        log(f'{path}: previous {prev} no longer queued, firing new')
    else:
        log(f'{path}: no previous, firing first')

    res = subprocess.run(cmd, stdout=subprocess.PIPE, check=False)

    # Pass stdout through so the scheduler log keeps the guid.
    sys.stdout.buffer.write(res.stdout)
    sys.stdout.flush()

    if res.returncode != 0:
        sys.exit(res.returncode)

    lines = [l.strip() for l in res.stdout.decode().splitlines() if l.strip()]

    if not lines:
        log(f'{path}: cmd exited 0 but produced no stdout; not updating etcd')
        sys.exit(0)

    new_id = lines[-1]
    etcd_put(path, new_id)
    log(f'{path}: stored {new_id}')


if __name__ == '__main__':
    main()
