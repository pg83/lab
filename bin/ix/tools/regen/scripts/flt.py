#!/usr/bin/env python3

import sys
import json
import collections
from functools import cmp_to_key
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'share' / 'ix' / 'regen'))

import libversion

groups = collections.defaultdict(list)

for l in sys.stdin.read().split('\n'):
    l = l.strip()

    if not l:
        continue

    rec = json.loads(l)

    if rec['ix_pkg_name'].startswith('bld/'):
        continue

    if len(rec['pkg_ver']) == 40:
        continue

    groups[rec['pkg_name']].append(rec)

def compare_versions(left, right):
    return libversion.version_compare(left, right, libversion.P_IS_PATCH, libversion.P_IS_PATCH)

def calc_max_ver(recs):
    return max((rec['pkg_ver'] for rec in recs), key=cmp_to_key(compare_versions))

def flt_ver(recs, ver):
    for x in recs:
        if x['pkg_ver'] == ver:
            yield x

for recs in groups.values():
    for rec in flt_ver(recs, calc_max_ver(recs)):
        print(json.dumps(rec))
