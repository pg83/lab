#!/usr/bin/env python3

"""
Pickle round-trip smoke test for every Service class registered in cg.py.

Why this exists separately from tst/test.py: the canon test loads cg.py via
`import cg`, which sets __module__='cg' on every class via Python's normal
module machinery. The cluster's ix Env.eval (ix/core/j2.py:213) instead does
`exec(code, ctx, ctx)` with no __name__ in ctx, leaving __module__='builtins'
and putting pickle on a different code path. The two paths can disagree;
canon won't catch render-only failures.

This script:
  1. Mimics Env.eval — exec cg.py source into a fresh ctx={}.
  2. Calls ctx['do'](code), which now anchors classes to sys.modules['cg'].
  3. Walks ClusterMap.it_cluster() and for every yielded service, exercises
     ctx['gen_runner'](srv) (= pickle.dumps under the hood) and round-trips
     the result through ctx['_Unpickler'] (= the runtime unpickle path).
  4. Asserts the recovered class name matches the original.

Failures here mean the next `ix mut system` will explode on render, or the
service will spawn fine but its first method dispatch will crash on unpickle.
Run before pushing any commit that touches Service classes or the
class/pickle plumbing in cg.py.

Run:
    python3 tst/dryrun.py

Exit 0 = every service round-trips. Exit 1 = at least one failed; details
on stderr.
"""

import base64
import io
import pathlib
import sys
import traceback


ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / 'lab' / 'cg.py').read_text()


ctx = {}
exec(SRC, ctx, ctx)
cconf = ctx['do'](SRC)


def round_trip(srv):
    runsh_b64 = ctx['gen_runner'](srv)
    runsh = base64.b64decode(runsh_b64).decode()
    pickle_b64 = runsh.split()[2]
    pkl_bytes = base64.b64decode(pickle_b64)

    return ctx['_Unpickler'](io.BytesIO(pkl_bytes)).load()


cm = ctx['ClusterMap'](cconf)
ok = 0
fail = []
seen = {}

for entry in cm.it_cluster():
    srv = entry['serv']
    cls_name = type(srv).__name__
    seen[cls_name] = seen.get(cls_name, 0) + 1

    try:
        loaded = round_trip(srv)

        if type(loaded['srv']).__name__ != cls_name:
            raise AssertionError(f'class identity mismatch: pickled {cls_name}, got {type(loaded["srv"]).__name__}')

        if loaded['hash'] != ctx['class_src_hash'](type(srv)):
            raise AssertionError(f'class_src_hash mismatch: pickle has {loaded["hash"]}, recompute gives {ctx["class_src_hash"](type(srv))}')

        ok += 1
    except Exception as e:
        fail.append((cls_name, srv, e, traceback.format_exc()))


print(f'classes: {len(seen)} unique, {sum(seen.values())} instances')
print(f'  {", ".join(f"{k}={v}" for k, v in sorted(seen.items()))}')
print(f'round-trips: {ok} OK, {len(fail)} FAIL')

for cls, srv, e, tb in fail:
    print(f'\n=== FAIL: {cls} (srv={srv!r}) ===', file=sys.stderr)
    print(tb, file=sys.stderr)

sys.exit(1 if fail else 0)
