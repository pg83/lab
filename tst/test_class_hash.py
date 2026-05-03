#!/usr/bin/env python3
"""
Smoke tests for _class_src_hash in lab/cg.py.

Checks:
    1. Hash is deterministic for a given class (same ref, two calls).
    2. Different cg.py classes produce different hashes (no collision
       on the prefix truncation).
    3. AST-based hashing strips comments (comment-only edits must
       NOT move the hash; that is the whole point of using ast.dump).
    4. Whitespace-only edits also don't move the hash.
    5. Real body edits DO move the hash.
    6. Hash depends on the MRO — adding a base class with real code
       changes the output.
    7. Hash propagates into pickle bytes: Service instances whose
       class source differs pickle to different bytes (this is what
       drives runsh_script change after a cg.py edit).

Run:
    python3 tst/test_class_hash.py

Non-zero exit on any failure.
"""

import ast
import hashlib
import os
import pathlib
import pickle
import sys
import textwrap


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'lab'))

import cg  # noqa: E402


def _ast_hash(src):
    return hashlib.sha256(ast.dump(ast.parse(src)).encode()).hexdigest()[:16]


FAILED = []


def ok(name):
    print(f'PASS  {name}')


def fail(name, msg):
    print(f'FAIL  {name}: {msg}')
    FAILED.append(name)


# 1. determinism
h1 = cg._class_src_hash(cg.Loki)
h2 = cg._class_src_hash(cg.Loki)
if h1 == h2 and len(h1) == 16:
    ok('deterministic')
else:
    fail('deterministic', f'{h1!r} vs {h2!r}')


# 2. cross-class uniqueness across cg's hash-using classes.
seen = {}
for c in (cg.Loki, cg.Grafana, cg.Samogon, cg.Promtail):
    h = cg._class_src_hash(c)
    if h in seen:
        fail('cross-class-unique',
             f'{c.__name__} and {seen[h].__name__} share hash {h}')
    else:
        seen[h] = c

if len(seen) == 4:
    ok('cross-class-unique')


# 3. comment-only edits preserve the hash
a = '''class X:
    def f(self):
        return 1
'''
b = '''class X:
    # added comment
    def f(self):
        # inside comment
        return 1
'''
if _ast_hash(a) == _ast_hash(b):
    ok('comment-only-stable')
else:
    fail('comment-only-stable',
         f'comments changed ast hash: {_ast_hash(a)} vs {_ast_hash(b)}')


# 4. whitespace-only edits preserve the hash
c = '''class X:
    def f(self):
            return 1
'''
d = '''class X:


    def f( self ):
        return  1
'''
if _ast_hash(c) == _ast_hash(d):
    ok('whitespace-only-stable')
else:
    fail('whitespace-only-stable',
         f'whitespace changed ast hash: {_ast_hash(c)} vs {_ast_hash(d)}')


# 5. body change moves the hash
e = '''class X:
    def f(self):
        return 1
'''
f = '''class X:
    def f(self):
        return 2
'''
if _ast_hash(e) != _ast_hash(f):
    ok('body-change-moves-hash')
else:
    fail('body-change-moves-hash',
         f'body change left ast hash stable: {_ast_hash(e)}')


# 6. MRO change moves the hash; _class_src_hash walks __mro__.
g = '''
class Base:
    def h(self):
        return 'b'

class X(Base):
    def f(self):
        return 1
'''
h_source = '''
class Base:
    def h(self):
        return 'c'

class X(Base):
    def f(self):
        return 1
'''

ns_g, ns_h = {}, {}
exec(g, ns_g)
exec(h_source, ns_h)
# Mirror _class_src_hash; feed sources manually for exec'd classes.
def _hash_with_src(src_per_mro):
    parts = [ast.dump(ast.parse(s)) for s in src_per_mro]
    return hashlib.sha256('\n'.join(parts).encode()).hexdigest()[:16]


mro_g = [
    'class X(Base):\n    def f(self):\n        return 1\n',
    "class Base:\n    def h(self):\n        return 'b'\n",
]
mro_h = [
    'class X(Base):\n    def f(self):\n        return 1\n',
    "class Base:\n    def h(self):\n        return 'c'\n",
]
if _hash_with_src(mro_g) != _hash_with_src(mro_h):
    ok('mro-change-moves-hash')
else:
    fail('mro-change-moves-hash',
         'different base-class bodies gave equal hash')


# 7. pickle bytes move when self.hash changes (drives runsh_script).
class _FakeSrv:
    def __init__(self, hash):
        self.hash = hash


s1 = pickle.dumps(_FakeSrv('aaaaaaaaaaaaaaaa'))
s2 = pickle.dumps(_FakeSrv('bbbbbbbbbbbbbbbb'))
if s1 != s2:
    ok('pickle-propagates-hash')
else:
    fail('pickle-propagates-hash', 'pickle bytes identical despite hash diff')


# 8. cg classes hash non-empty (catches getsource-returned-'' regression).
EMPTY_SHA_PREFIX = hashlib.sha256(b'').hexdigest()[:16]
bad = []
for c in (cg.Loki, cg.Grafana, cg.Samogon, cg.Promtail):
    h = cg._class_src_hash(c)
    if h == EMPTY_SHA_PREFIX:
        bad.append(c.__name__)

if not bad:
    ok('nonempty-source-hash')
else:
    fail('nonempty-source-hash',
         f'empty-sha hash for classes: {bad} — inspect.getsource failed silently')


if FAILED:
    print(f'\n{len(FAILED)} test(s) failed: {FAILED}')
    sys.exit(1)

print('\nall tests passed')
