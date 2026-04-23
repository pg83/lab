#!/usr/bin/env python3

"""
ci — worker-side CI build runner. No more scheduling: the dispatch
loop lives in job_scheduler via /etc/cron/*.json files that ignite
a fresh gorn task per tier per tick (deduped by the dedup wrapper
against /ci/<tier>).

Subcommands:

  ci check <tier>
      Fresh clone of https://github.com/pg83/ix at its current
      HEAD sha, run `./ix build <tier> --seed=1` via molot. Exits
      0 if the build reached completion — including target-build
      failures, detected by marker strings in captured output
      (molot "node failed", ix "ERROR <descr>", etc.). Any other
      non-zero exit (clone died, binary missing, molot crashed) is
      an infra failure: paired with gorn's --retry-error in the
      cron dispatch so the leader puts the task back on the queue.

  ci update <local_cache_path>
      Reads a local molot-cache from <local_cache_path>, unions
      it with the shared cix/complete object in S3, writes the
      union back. Intended to be invoked under `etcdctl lock
      /lock/ci/cache` from ci check at the end of each build.
      Takes the path as argv instead of stdin because etcdctl
      lock eats stdin before handing off to its child cmd.
"""

import json
import os
import re
import shutil
import subprocess
import sys


GIT_URL = 'https://github.com/pg83/ix'

CACHE_LOCK_KEY = '/lock/ci/cache'
CACHE_S3_BUCKET = 'cix'
CACHE_S3_KEY = 'complete'
MC_ALIAS = 'cix'

# Marker strings that mean "./ix build got far enough to dispatch a
# target, the target blew up". Seeing any of these in captured stdout
# + stderr means the build actually ran, so ci-check exits 0 regardless
# of ./ix's own non-zero exit. Anything else = infra error.
TARGET_FAIL_PATTERNS = [
    # ix/core/execute.py ERROR banner before `os.kill(0, SIGKILL)` when
    # a local assemble cmd fails (IX_EXEC_KIND=local).
    re.compile(rb'^ERROR ', re.MULTILINE),
    # molot/executor.go:91 red banner on stderr when a node future
    # resolves to an error.
    re.compile(rb'^node failed: ', re.MULTILINE),
    # molot/dispatch.go quiet-mode banners around node logs.
    re.compile(rb'^---- stdout of failed node ', re.MULTILINE),
    re.compile(rb'^---- stderr of failed node ', re.MULTILINE),
    # molot/dispatch.go:159 ThrowFmt message surfaced by main.
    re.compile(rb'failed via gorn ignite', re.MULTILINE),
]


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def git_ls_remote_head(url):
    res = subprocess.run(
        ('git', 'ls-remote', '--quiet', url, 'HEAD'),
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )

    return res.stdout.split()[0]


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
    """Fetch S3 object bytes. Returns empty bytes on 'object does not
    exist' (first run before anyone's pushed a cache); any other
    failure bubbles up."""
    res = subprocess.run(
        ('minio-client', 'cat', uri),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if res.returncode == 0:
        return res.stdout

    if b'Object does not exist' in res.stderr or b'NoSuchKey' in res.stderr:
        return b''

    sys.stderr.buffer.write(res.stderr)
    res.check_returncode()


def update(local_path):
    """Merge <local_path> (caller's local cache file) with the shared
    <bucket>/complete in S3 and push the union back. Expected to be
    run under `etcdctl lock /lock/ci/cache` — no locking here.
    Pure read-modify-write, single S3 PUT."""
    env = mc_env_for(os.environ)
    uri = s3_cache_uri()

    with open(local_path) as f:
        ours = f.read()

    remote = mc_cat(uri, env).decode()

    merged = set()

    for blob in (remote, ours):
        for line in blob.splitlines():
            line = line.strip()

            if line:
                merged.add(line)

    tmp = os.path.abspath(f'ci-complete.{os.getpid()}.tmp')

    try:
        with open(tmp, 'w') as f:
            for line in sorted(merged):
                f.write(line + '\n')

        subprocess.run(
            ('minio-client', 'cp', tmp, uri),
            env=env,
            check=True,
        )
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    log(f'ci update: local={len(ours.splitlines())} + remote={len(remote.splitlines())} → {len(merged)}')


def check(tier):
    # Workdir = PWD (the endpoint path gorn chdir'd us into). Clone
    # into `./ix` under it and run from there. rmtree first so a
    # leftover from a prior task on this endpoint doesn't interfere.
    workdir = 'ix'

    if os.path.exists(workdir):
        shutil.rmtree(workdir)

    sha = git_ls_remote_head(GIT_URL)
    log(f'check {tier}: HEAD={sha}')

    subprocess.run(('git', 'clone', GIT_URL, workdir), check=True)
    subprocess.run(('git', '-C', workdir, 'checkout', sha), check=True)

    env = os.environ.copy()
    env['IX_EXEC_KIND'] = 'molot'
    env.setdefault('S3_BUCKET', 'gorn')

    # Molot-complete cache: pull the shared union from S3, hand it to
    # molot as its local cache, push any additions back via `ci update`
    # at the end. Absolute path because molot's cwd is workdir.
    cache_path = os.path.abspath(os.path.join(workdir, 'cache'))
    env['MOLOT_CACHE'] = cache_path
    mc_env = mc_env_for(env)

    # Seed needs no lock — MinIO GET is atomic, whatever we read is a
    # consistent snapshot. Racing with a concurrent update means we
    # miss a few entries; next run picks them up.
    with open(cache_path, 'wb') as f:
        f.write(mc_cat(s3_cache_uri(), mc_env))

    log(f'seeded cache_path={cache_path} size={os.path.getsize(cache_path)}'
        f' IX_EXEC_KIND={env.get("IX_EXEC_KIND")} MOLOT_CACHE={env.get("MOLOT_CACHE")}')

    # start_new_session=True: ./ix build's execute.py does
    # `os.kill(0, SIGKILL)` on target-subprocess failure, which kills
    # its entire process group. Without a new session, that group
    # includes us — we'd be dead before we could classify the failure.
    try:
        res = subprocess.run(
            ('./ix', 'build', tier, '--seed=1'),
            cwd=workdir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            check=False,
        )
    finally:
        # Always push our additions back — even a partial build built
        # some nodes and those wins are worth sharing. RMW is
        # serialized across concurrent checks via etcdctl lock around
        # `ci update`, which reads the cache path from argv (stdin is
        # eaten by etcdctl lock before reaching its child). Don't
        # swallow failures — we want the traceback in the task stderr.
        size = os.path.getsize(cache_path) if os.path.exists(cache_path) else '-'
        log(f'merging cache_path={cache_path} size={size}')

        subprocess.run(
            ('etcdctl', 'lock', CACHE_LOCK_KEY, '--',
             'ci', 'update', cache_path),
            env=mc_env,
            check=True,
        )

    # Replay build output to our own stderr so gorn wrap's capture
    # picks it up and ships it to S3 alongside result.json.
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
        print('usage: ci {check <tier> | update}', file=sys.stderr)
        sys.exit(2)

    cmd = sys.argv[1]

    if cmd == 'check':
        if len(sys.argv) != 3:
            print('usage: ci check <tier>', file=sys.stderr)
            sys.exit(2)

        check(sys.argv[2])
        return

    if cmd == 'update':
        if len(sys.argv) != 3:
            print('usage: ci update <local_cache_path>', file=sys.stderr)
            sys.exit(2)

        update(sys.argv[2])
        return

    print(f'unknown subcommand: {cmd}', file=sys.stderr)
    sys.exit(2)


if __name__ == '__main__':
    main()
