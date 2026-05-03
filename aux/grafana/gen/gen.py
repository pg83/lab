#!/usr/bin/env python3
# Walks share/metrics/*.json and emits grafana-provisioning dashboards.

import glob
import json
import os
import sys


REALM = os.getcwd()
IN_DIR = os.path.join(REALM, 'share', 'metrics')
OUT_DIR = os.path.join(REALM, 'share', 'grafana-provisioning', 'dashboards-json')

PANEL_W = 12
PANEL_H = 6


def _targets_counter(metric, by):
    if by:
        by_clause = 'sum by (' + ', '.join(by) + ')'
        legend = ' '.join('{{' + b + '}}' for b in by)
    else:
        by_clause = 'sum'
        legend = metric

    return [{
        'refId': 'A',
        'expr': f'{by_clause} (rate({metric}[1m]))',
        'legendFormat': legend,
    }]


def _targets_histogram(metric, quantiles):
    targets = []

    for i, q in enumerate(quantiles):
        targets.append({
            'refId': chr(ord('A') + i),
            'expr': f'histogram_quantile({q}, sum by (le) (rate({metric}_bucket[1m])))',
            'legendFormat': f'p{int(round(q * 100))}',
        })

    return targets


def _targets_gauge(metric, by):
    if by:
        by_clause = 'sum by (' + ', '.join(by) + ')'
        legend = ' '.join('{{' + b + '}}' for b in by)
    else:
        by_clause = 'sum'
        legend = metric

    return [{
        'refId': 'A',
        'expr': f'{by_clause} ({metric})',
        'legendFormat': legend,
    }]


def build_panel(idx, p):
    x = 0 if idx % 2 == 0 else PANEL_W
    y = (idx // 2) * PANEL_H

    title = p['title']
    ptype = p['type']
    metric = p['metric']

    unit = p.get('unit')

    if ptype == 'counter':
        targets = _targets_counter(metric, p.get('by'))
        unit = unit or 'ops'
    elif ptype == 'histogram':
        targets = _targets_histogram(metric, p.get('quantiles', [0.5, 0.95, 0.99]))
        unit = unit or 's'
    elif ptype == 'gauge':
        targets = _targets_gauge(metric, p.get('by'))
    else:
        raise ValueError(f'grafana-gen: unknown panel type {ptype!r} in {p!r}')

    panel = {
        'id': idx + 1,
        'title': title,
        'type': 'timeseries',
        'gridPos': {'x': x, 'y': y, 'w': PANEL_W, 'h': PANEL_H},
        'datasource': {'type': 'prometheus', 'uid': 'prom'},
        'targets': targets,
    }

    if unit:
        panel['fieldConfig'] = {'defaults': {'unit': unit}}

    return panel


def build_dashboard(manifest):
    service = manifest['service']

    return {
        'uid': manifest.get('uid', service),
        'title': manifest.get('title', service),
        'tags': manifest.get('tags', [service]),
        'schemaVersion': 39,
        'version': 1,
        'editable': True,
        'graphTooltip': 0,
        'time': {'from': 'now-15m', 'to': 'now'},
        'timepicker': {},
        'timezone': '',
        'refresh': '10s',
        'annotations': {'list': []},
        'templating': {'list': []},
        'links': [],
        'panels': [build_panel(i, p) for i, p in enumerate(manifest['panels'])],
    }


def main():
    if not os.path.isdir(IN_DIR):
        print(f'grafana-gen: no {IN_DIR}, nothing to do', file=sys.stderr)

        return

    os.makedirs(OUT_DIR, exist_ok=True)

    for manifest_path in sorted(glob.glob(os.path.join(IN_DIR, '*.json'))):
        with open(manifest_path) as f:
            manifest = json.load(f)

        dashboard = build_dashboard(manifest)

        out_path = os.path.join(OUT_DIR, manifest['service'] + '.json')

        with open(out_path, 'w') as f:
            json.dump(dashboard, f, indent=2, sort_keys=True)

        print(f'grafana-gen: {manifest_path} -> {out_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
