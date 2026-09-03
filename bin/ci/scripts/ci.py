#!/usr/bin/env python3

"""
ci — worker-side CI build runner. No more scheduling: the dispatch
loop lives in job_scheduler via /etc/cron/*.json files that ignite
a fresh gorn task per tier per tick (deduped by the dedup wrapper
against /ci/<tier>).

Subcommands:

  ci check <tier> <sha>
      Fresh clone of the local ogorod ix mirror at its current
      HEAD sha, run `./ix build <tier> --seed=1` via molot. Exits
      0 if the build reached completion — including target-build
      failures, detected by marker strings in captured output
      (molot "node failed", ix "ERROR <descr>", etc.). Any other
      non-zero exit (clone died, binary missing, molot crashed) is
      an infra failure: gorn drops it as non-retriable, the
      job_scheduler's 5s cron tick + dedup re-fires it on the next
      pass — no --retry-error needed. Seeds the disposable local
      Molot cache from the complete UID snapshot at s3://molot/complete.
"""

import json
import os
import re
import shutil
import subprocess
import sys


GIT_URL = 'http://127.0.0.1:8035/mirror_ix.git'

CACHE_S3_BUCKET = 'molot'
CACHE_S3_KEY = 'complete'
MC_ALIAS = 'molot_cache'

# Markers: target ran but failed → exit 0; their absence = infra error.
TARGET_FAIL_PATTERNS = [
    re.compile(rb'^ERROR ', re.MULTILINE),
    re.compile(rb'^node failed: ', re.MULTILINE),
    re.compile(rb'^---- stdout of failed node ', re.MULTILINE),
    re.compile(rb'^---- stderr of failed node ', re.MULTILINE),
    re.compile(rb'failed via gorn ignite', re.MULTILINE),
]


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def has_target_fail(blob):
    return any(p.search(blob) for p in TARGET_FAIL_PATTERNS)


def mc_env_for(base_env):
    """Build an env dict with MC_HOST_<alias> baked from S3_ENDPOINT +
    AWS_* so minio-client can reach the cluster without ~/.mc/config."""
    scheme, host = base_env['S3_ENDPOINT'].split('://', 1)
    key = base_env['AWS_ACCESS_KEY_ID']
    secret = base_env['AWS_SECRET_ACCESS_KEY']
    out = dict(base_env)
    out[f'MC_HOST_{MC_ALIAS}'] = f'{scheme}://{key}:{secret}@{host}'
    return out


def s3_cache_uri():
    return f'{MC_ALIAS}/{CACHE_S3_BUCKET}/{CACHE_S3_KEY}'


def mc_cat(uri, env):
    """Fetch the complete UID snapshot from S3."""
    return subprocess.run(
        ('minio-client', 'cat', uri),
        env=env,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout


def graph_signature(g):
    return (
        sorted(n['uid'] for n in g['nodes']),
        sorted(g['targets']),
    )


def dump_graph(workdir, tier, env):
    res = subprocess.run(
        ('./ix', 'build', tier, '--seed=1'),
        cwd=workdir,
        env={**env, 'IX_DUMP_GRAPH': '1'},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if res.returncode != 0:
        sys.stderr.buffer.write(res.stderr)
        log(f'IX_DUMP_GRAPH failed (rc={res.returncode})')
        return None

    return json.loads(res.stdout)


def graph_unchanged_from_parent(workdir, tier, env, sha):
    parent_res = subprocess.run(
        ('git', '-C', workdir, 'rev-parse', f'{sha}^'),
        capture_output=True, text=True, check=False,
    )

    if parent_res.returncode != 0:
        log(f'no parent revision for {sha}; cannot diff graphs')
        return False

    parent_sha = parent_res.stdout.strip()
    log(f'graph diff: {parent_sha} -> {sha}')

    g_curr = dump_graph(workdir, tier, env)

    if g_curr is None:
        return False

    subprocess.run(('git', '-C', workdir, 'checkout', parent_sha), check=True)

    try:
        g_prev = dump_graph(workdir, tier, env)
    finally:
        subprocess.run(('git', '-C', workdir, 'checkout', sha), check=True)

    if g_prev is None:
        return False

    sig_curr = graph_signature(g_curr)
    sig_prev = graph_signature(g_prev)

    log(f'sha={sha}: nodes={len(sig_curr[0])} targets={len(sig_curr[1])}')
    log(f'parent={parent_sha}: nodes={len(sig_prev[0])} targets={len(sig_prev[1])}')

    return sig_curr == sig_prev


def check(tier, sha):
    workdir = 'ix'

    if os.path.exists(workdir):
        shutil.rmtree(workdir)

    log(f'check {tier}: HEAD={sha}')

    subprocess.run(('git', 'clone', GIT_URL, workdir), check=True)
    subprocess.run(('git', '-C', workdir, 'checkout', sha), check=True)

    env = os.environ.copy()
    env['IX_EXEC_KIND'] = 'molot'
    env.setdefault('S3_BUCKET', 'molot')
    cache_mc_env = mc_env_for(env)

    if graph_unchanged_from_parent(workdir, tier, env, sha):
        log(f'graph unchanged from parent for tier={tier}; skipping molot run')
        sys.exit(0)

    cache_path = os.path.abspath(os.path.join(workdir, 'cache'))
    env['MOLOT_CACHE'] = cache_path

    with open(cache_path, 'wb') as f:
        f.write(mc_cat(s3_cache_uri(), cache_mc_env))

    log(f'seeded cache_path={cache_path} size={os.path.getsize(cache_path)}'
        f' IX_EXEC_KIND={env.get("IX_EXEC_KIND")} MOLOT_CACHE={env.get("MOLOT_CACHE")}')

    # New session: ./ix's execute.py SIGKILLs its pgrp; we must not be in it.
    res = subprocess.run(
        ('./ix', 'build', tier, '--seed=1'),
        cwd=workdir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        check=False,
    )

    # Replay to stderr so gorn wrap captures it alongside result.json.
    os.write(2, res.stdout)

    if res.returncode == 0:
        log('ix build succeeded')
        sys.exit(0)

    if has_target_fail(res.stdout):
        log(f'ix build exited {res.returncode} with target-failure marker — counted as build error (ci check success)')
        sys.exit(0)

    log(f'ix build exited {res.returncode} with no target-failure marker — infra error')
    sys.exit(res.returncode)


def main():
    if len(sys.argv) < 2:
        print('usage: ci check <tier> <sha>', file=sys.stderr)
        sys.exit(2)

    cmd = sys.argv[1]

    if cmd == 'check':
        if len(sys.argv) != 4:
            print('usage: ci check <tier> <sha>', file=sys.stderr)
            sys.exit(2)

        check(sys.argv[2], sys.argv[3])
        return

    print(f'unknown subcommand: {cmd}', file=sys.stderr)
    sys.exit(2)


if __name__ == '__main__':
    main()
