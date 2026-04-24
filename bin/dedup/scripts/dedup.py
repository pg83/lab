#!/usr/bin/env python3

"""
dedup --root <ROOT> <etcd_path> -- <cmd...>

Single-flight helper for fire-and-forget tools that emit a task id
on stdout (primary target: `gorn ignite` without --wait). Reads
<etcd_path> via etcdctl; if it holds a guid of a task still queued
in gorn ($GORN_API), exits 0 without re-firing — the previous
dispatch hasn't drained yet, no point stacking another on top.

Otherwise runs <cmd>, passes its stdout through untouched, and on
success writes the last non-empty stdout line back into <etcd_path>.

--root must match the --root that <cmd> uses when ignite'ing into
gorn. gorn /v1/tasks/<guid> requires ?root= to know where to look
on S3 for the "done" fallback; pass the same one here so state
lookups work for both "queued" and "done" tasks.

Usage in practice — cron-file `cmd` array, under etcdctl lock so
two schedulers can't race the read-check-write:

    etcdctl lock /lock/ci/tier_0 \\
        dedup --root ci /ci/tier_0 -- \\
            gorn ignite --root ci --env AWS_ACCESS_KEY_ID=$... \\
                -- /bin/env PATH=/bin ci check set/ci/tier/0

Exit policy:
  - previous guid still `queued` → exit 0, skip.
  - no previous / previous `done` / `not_found` → run cmd.
  - gorn API unreachable → propagate the error (non-zero exit)
    so the scheduler retries the next tick instead of silently
    dropping dispatches on cluster hiccups.
"""

import json
import os
import subprocess
import sys
import urllib.parse
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


def gorn_state(guid, root):
    api = os.environ['GORN_API'].rstrip('/')
    url = f'{api}/v1/tasks/{guid}?root=' + urllib.parse.quote(root, safe='')

    with urllib.request.urlopen(url, timeout=10) as resp:
        body = resp.read()

    return json.loads(body).get('state', '')


def usage():
    print('usage: dedup --root <ROOT> <etcd_path> -- <cmd...>', file=sys.stderr)
    sys.exit(2)


def main():
    args = sys.argv[1:]

    if len(args) < 2 or args[0] != '--root':
        usage()

    root = args[1]
    rest = args[2:]

    if len(rest) < 3 or rest[1] != '--':
        usage()

    path = rest[0]
    cmd = rest[2:]

    prev = etcd_get(path)

    if prev:
        state = gorn_state(prev, root)

        if state == 'queued':
            log(f'{path}: {prev} still queued, skipping')
            sys.exit(0)

        log(f'{path}: previous {prev} is {state!r}, firing new')
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
