#!/usr/bin/env python3

"""
Cluster log follower.

Polls each tail_log endpoint (http://lab{1,2,3}.nebula:8040) once
per second, detects what's new since the last poll via md5-of-line
uids kept per-endpoint, merges the union across endpoints, sorts by
ts, prints each uid at most once. Override endpoints via
LOG_FOLLOW_ENDPOINTS (comma-separated URLs).

Doubling lookback: start with n=1, retry with n*=2 until the response
contains a uid we've already seen (= boundary, everything older is
already covered) or we hit tail_log's ~50k ring cap. Keeps per-tick
work proportional to the actual arrival rate, not to buffer size.

On cold start the first tick hits the cap and prints every buffered
line, sorted; every subsequent tick prints only the delta.
"""

import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request


DEFAULT_EPS = ','.join([
    'http://lab1.nebula:8040',
    'http://lab2.nebula:8040',
    'http://lab3.nebula:8040',
])

ENDPOINTS = os.environ.get('LOG_FOLLOW_ENDPOINTS', DEFAULT_EPS).split(',')

# tail_log's in-memory deque is maxlen=50_000; doubling past that
# just returns the same buffer twice.
DEPTH_CAP = 50000
POLL_INTERVAL_S = 1.0


def uid_of(raw_line):
    return hashlib.md5(raw_line.encode()).hexdigest()


def label_of(ep):
    # http://<host>:<port> → <host> (strip scheme, strip port, strip
    # the `.nebula` suffix if present for compact output).
    hostport = ep.split('://', 1)[-1]
    host = hostport.rsplit(':', 1)[0]

    if host.endswith('.nebula'):
        host = host[:-len('.nebula')]

    return host


def short_path(p):
    # /var/run/<service>/std/<file> → <service>/<file>
    segs = p.split('/')

    if len(segs) >= 5 and segs[1] == 'var' and segs[2] == 'run':
        return '/'.join(segs[3:])

    return p


def fetch(ep, n):
    q = urllib.parse.urlencode({'n': n})

    with urllib.request.urlopen(f'{ep}/?{q}', timeout=5) as resp:
        return resp.read().decode('utf-8', errors='replace')


def parse_response(body):
    out = []

    for raw in body.splitlines():
        raw = raw.strip()

        if not raw:
            continue

        try:
            rec = json.loads(raw)
        except Exception:
            continue

        out.append((uid_of(raw), rec))

    return out


def poll_new(ep, seen_ep):
    n = 1

    while True:
        try:
            body = fetch(ep, n)
        except Exception as e:
            print(f'! {label_of(ep)}: {e}', file=sys.stderr, flush=True)
            return []

        recs = parse_response(body)

        if not recs:
            return []

        uids = {u for u, _ in recs}

        # Any overlap with the last-known set means we've reached the
        # point where new and old meet; everything older is covered.
        if seen_ep & uids:
            return [(u, r) for u, r in recs if u not in seen_ep]

        # No overlap yet: cold start, or the window we asked for is
        # still entirely newer than everything we've seen. Double and
        # retry, unless we already hit the ring cap or the server
        # returned fewer entries than requested (= buffer exhausted,
        # all of it is fresh).
        if n >= DEPTH_CAP or len(recs) < n:
            return recs

        n = min(n * 2, DEPTH_CAP)


def main():
    seen_per_ep = {ep: set() for ep in ENDPOINTS}
    seen_global = set()

    while True:
        fresh = []

        for ep in ENDPOINTS:
            for uid, rec in poll_new(ep, seen_per_ep[ep]):
                seen_per_ep[ep].add(uid)

                if uid in seen_global:
                    continue

                seen_global.add(uid)
                fresh.append((rec.get('ts', 0.0), ep, rec))

        fresh.sort(key=lambda x: x[0])

        for ts, ep, rec in fresh:
            human_ts = time.strftime('%H:%M:%S', time.localtime(ts))
            print(
                f'{human_ts} {label_of(ep)} '
                f'{short_path(rec.get("path", "?"))[:35]:35} '
                f'{rec.get("line", "")}',
                flush=True,
            )

        time.sleep(POLL_INTERVAL_S)


if __name__ == '__main__':
    main()
