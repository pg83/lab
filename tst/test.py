#!/usr/bin/env python3

"""
Dump the full cluster config produced by lab/cg.py:do() as canonical JSON.

Canonicalize:
    python3 tst/test.py > tst/canon.json

Check against canon:
    python3 tst/test.py | diff tst/canon.json -
"""

import hashlib
import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / 'lab'))

import cg


def shorten(s):
    def sub(m):
        return 'sha256:' + hashlib.sha256(m.group(1).encode()).hexdigest()[:16]

    return re.sub(r'([A-Za-z0-9+/]{64,}={0,2})', sub, s)


code = (ROOT / 'lab' / 'cg.py').read_text()
cconf = cg.do(code)

for h in cconf['hosts']:
    h['extra'] = [shorten(line) for line in h['extra'].split('\n')]

json.dump(cconf, sys.stdout, indent=4, sort_keys=True, default=str)
sys.stdout.write('\n')
