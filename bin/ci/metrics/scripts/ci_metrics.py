#!/usr/bin/env python3

"""
ci_metrics — incremental scan of recent CI task results in S3,
classify each one, push structured event lines to Loki for the
CI dashboard. Cursor (max processed result.json mtime) is held
in etcd at /ci_metrics/cursor — restart-safe and idempotent.

Each tick:
  1. Read cursor from etcd. Empty → bootstrap to "now" so the
     first tick doesn't backfill the entire S3 history.
  2. List minio/gorn/ci/<guid>/result.json with mtime > cursor.
  3. For each new task: parse result.json + stderr, classify into
     {success, target_fail, infra_error}, extract failed pkg name
     and tier from ci.py's existing log lines. No protocol change
     in ci.py.
  4. POST one batched payload to http://127.0.0.1:8032/loki/api/v1/push
     with stream {service="ci_metrics"}. Loki on the local host
     gossips it across the ring. Use 127.0.0.1 (not localhost) to
     dodge the resolver-flap we hit in `cache_ix_sources`.
  5. Advance cursor to max mtime seen.

Fired by job_scheduler via gorn ignite (per the lab convention),
so the work runs in a worker's tmpfs ns and doesn't bump against
the scheduler's 10s timeout.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone


CURSOR_KEY = '/ci_metrics/cursor'
LOKI_URL = 'http://127.0.0.1:8032/loki/api/v1/push'
S3_PREFIX = 'minio/gorn/ci/'


# Order matters: ci.py emits "succeeded" only on the happy path; the
# two "exited" variants are mutually exclusive past that.
CLASS_MARKERS = [
    (re.compile(rb'^\+ ix build succeeded$', re.MULTILINE), 'success'),
    (re.compile(rb'^\+ ix build exited \d+ with target-failure marker', re.MULTILINE), 'target_fail'),
    (re.compile(rb'^\+ ix build exited \d+ with no target-failure marker', re.MULTILINE), 'infra_error'),
]

NODE_FAIL_RE = re.compile(rb'node failed: node \S+ \(out=/ix/store/\w+-(\S+?)\)')

TIER_RE = re.compile(rb'^\+ check (set/ci/tier/\d+):', re.MULTILINE)


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def mc_env():
    scheme, host = os.environ['S3_ENDPOINT'].split('://', 1)
    env = dict(os.environ)
    env['MC_HOST_minio'] = f"{scheme}://{os.environ['AWS_ACCESS_KEY_ID']}:{os.environ['AWS_SECRET_ACCESS_KEY']}@{host}"
    return env


def etcd_get(key):
    res = subprocess.run(
        ['etcdctl', 'get', key, '--print-value-only'],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return res.stdout.strip()


def etcd_put(key, value):
    subprocess.run(['etcdctl', 'put', key, value], check=True)


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def list_results(env, cursor):
    res = subprocess.run(
        ['minio-client', 'ls', '--recursive', '--json', S3_PREFIX],
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )

    out = []

    for line in res.stdout.splitlines():
        rec = json.loads(line)
        key = rec.get('key', '')

        if not key.endswith('/result.json'):
            continue

        ts = rec['lastModified']

        if ts <= cursor:
            continue

        guid = key.rsplit('/', 1)[0]
        out.append((ts, guid))

    out.sort()
    return out


def fetch(env, key):
    return subprocess.check_output(
        ['minio-client', 'cat', f'{S3_PREFIX}{key}'],
        env=env,
    )


def classify(stderr_bytes):
    cls = 'unknown'

    for pat, name in CLASS_MARKERS:
        if pat.search(stderr_bytes):
            cls = name
            break

    failed = ''
    matches = NODE_FAIL_RE.findall(stderr_bytes)

    if matches:
        # The ci.py classifier looks at the LAST node failure to set
        # the marker, so report the same one for consistency.
        failed = matches[-1].decode()

    tier = ''
    m = TIER_RE.search(stderr_bytes)

    if m:
        tier = m.group(1).decode()

    return cls, failed, tier


def iso_to_ns(iso):
    # finished_at is e.g. "2026-04-26T01:00:00.123456789Z"; nanos may
    # be present. datetime.fromisoformat handles up to microseconds,
    # so trim sub-microsecond digits before parsing.
    s = iso.replace('Z', '+00:00')

    if '.' in s:
        head, tail = s.rsplit('.', 1)
        # tail is "<frac>+00:00"; cap the fractional part at 6 digits
        frac, tz = tail.split('+', 1) if '+' in tail else (tail, None)
        frac = frac[:6]
        s = f'{head}.{frac}' + (f'+{tz}' if tz else '')

    return int(datetime.fromisoformat(s).timestamp() * 1e9)


def push_loki(events):
    body = {
        'streams': [
            {
                'stream': {'service': 'ci_metrics'},
                'values': events,
            },
        ],
    }

    req = urllib.request.Request(
        LOKI_URL,
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status >= 300:
            raise Exception(f'loki push: {resp.status} {resp.read()}')


def main():
    env = mc_env()
    cursor = etcd_get(CURSOR_KEY)

    if not cursor:
        # First run — don't backfill the entire S3 history. Pin cursor
        # to "now" and start tracking from the next tick.
        cursor = now_iso()
        etcd_put(CURSOR_KEY, cursor)
        log(f'bootstrapped cursor to {cursor!r}')
        return

    log(f'cursor: {cursor!r}')

    new = list_results(env, cursor)
    log(f'new tasks: {len(new)}')

    if not new:
        return

    events = []
    max_ts = cursor

    for ts, guid in new:
        result = json.loads(fetch(env, f'{guid}/result.json'))
        stderr = fetch(env, f'{guid}/stderr')
        cls, failed_node, tier = classify(stderr)

        ev = {
            'ev': 'ci_done',
            'guid': guid,
            'tier': tier,
            'host': result.get('host', ''),
            'user': result.get('user', ''),
            'exit': result.get('exit_code'),
            'class': cls,
            'failed_node': failed_node,
            'dur': result.get('duration_sec'),
            'finished_at': result.get('finished_at', ''),
        }

        ts_ns = str(iso_to_ns(result.get('finished_at') or ts))
        events.append([ts_ns, json.dumps(ev)])

        if ts > max_ts:
            max_ts = ts

    log(f'pushing {len(events)} events to loki')
    push_loki(events)

    etcd_put(CURSOR_KEY, max_ts)
    log(f'cursor advanced to {max_ts!r}')


if __name__ == '__main__':
    main()
