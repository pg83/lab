#!/usr/bin/env python3

"""
Pearson + lagged cross-correlation between two PromQL time series.

Pulls both queries over the same range from the Federator (defaults
to lab1:8030), aligns on a shared time grid, then for every pair of
returned series (after any Prom labels split the query) prints:

  - instant Pearson r (no lag)
  - cross-correlation peak across ±max_lag steps and its lag in seconds
    (positive lag = B lags A, i.e. A precedes B by that many seconds)

Pure stdlib — urllib + math. No pandas/scipy dependency.

Example:
  xcorr --since=3h \\
    'rate(nebula_nebula_udp_0_drops{job="nebula_node"}[5m])' \\
    'changes(etcd_server_leader_changes_seen_total{job="etcd_private"}[5m])'
"""

import argparse
import json
import math
import sys
import time
import urllib.parse
import urllib.request


UNIT = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}


def log(*args):
    print(*args, file=sys.stderr, flush=True)


def fetch(api, query, start, end, step):
    target = api.rstrip('/') + '/api/v1/query_range?' + urllib.parse.urlencode({
        'query': query, 'start': start, 'end': end, 'step': step,
    })

    with urllib.request.urlopen(target, timeout=30) as resp:
        doc = json.load(resp)

    if doc.get('status') != 'success':
        raise SystemExit(f'query failed: {doc}')

    out = {}

    for s in doc['data']['result']:
        m = s['metric']
        key = ','.join(f'{k}={v}' for k, v in sorted(m.items()) if k != '__name__') or '(no labels)'
        out[key] = {float(t): float(v) for t, v in s['values']}

    return out


def pearson(xs, ys):
    n = len(xs)

    if n < 2:
        return float('nan')

    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))

    if sxx == 0 or syy == 0:
        return float('nan')

    return sxy / math.sqrt(sxx * syy)


def cross_corr(xs, ys, max_lag):
    # Positive lag k: A precedes B by k.
    n = len(xs)
    out = []

    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            a, b = xs[-lag:], ys[:lag]
        elif lag > 0:
            a, b = xs[:-lag], ys[lag:]
        else:
            a, b = xs, ys

        if len(a) < 10:
            continue

        out.append((lag, pearson(a, b)))

    return out


def parse_duration(s):
    if not s or s[-1] not in UNIT:
        raise SystemExit(f'bad --since {s!r}; expect e.g. 30m, 3h, 1d')

    return int(s[:-1]) * UNIT[s[-1]]


def main():
    ap = argparse.ArgumentParser(description='PromQL cross-correlation (pure stdlib).')
    ap.add_argument('--api', default='http://10.1.1.2:8030', help='Prometheus/Federator URL')
    ap.add_argument('--since', default='1h', help='window, e.g. 30m / 3h / 1d')
    ap.add_argument('--step', type=int, default=15, help='sampling step in seconds')
    ap.add_argument('--max-lag', type=int, default=20, help='±lag steps to scan')
    ap.add_argument('a', help='PromQL A')
    ap.add_argument('b', help='PromQL B')
    args = ap.parse_args()

    end = int(time.time())
    start = end - parse_duration(args.since)

    a_map = fetch(args.api, args.a, start, end, args.step)
    b_map = fetch(args.api, args.b, start, end, args.step)

    log(f'# A = {args.a}  ({len(a_map)} series)')
    log(f'# B = {args.b}  ({len(b_map)} series)')
    log(f'# window={args.since}  step={args.step}s  max_lag=±{args.max_lag * args.step}s')
    log()

    for ka, a in a_map.items():
        for kb, b in b_map.items():
            common = sorted(set(a) & set(b))

            if len(common) < 20:
                log(f'SKIP {ka} × {kb}: only {len(common)} common samples')

                continue

            xs = [a[t] for t in common]
            ys = [b[t] for t in common]
            r0 = pearson(xs, ys)
            xc = cross_corr(xs, ys, args.max_lag)
            best_lag, best_r = max(xc, key=lambda p: abs(p[1]))
            lag_s = best_lag * args.step
            print(f'pearson={r0:+.3f}  best_lag={lag_s:+5d}s (r={best_r:+.3f})  A~[{ka}]  B~[{kb}]')


if __name__ == '__main__':
    main()
