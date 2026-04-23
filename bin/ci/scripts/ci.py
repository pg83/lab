#!/usr/bin/env python3

"""
ci — cluster CI orchestrator.

Subcommands:

  ci serve
      Poll GitHub, dispatch per-tier build tasks through gorn, advance
      the /ci/last_sha pointer in etcd when a sha has been fully
      checked. Designed to run on every lab host wrapped in
      `etcdctl lock /lock/ci` so only one instance actually polls at a
      time; peers block inside etcdctl until the holder dies.

  ci check <tier> <sha>
      Fresh clone of the ix repo at <sha>, run `./ix build <tier>
      --seed=1` via molot. Exits 0 if the build completed, including
      target-build failures — those are recognized by marker strings in
      captured output (molot "node failed", ix "ERROR <descr>", etc.).
      Any other non-zero exit (clone died, binary missing, molot itself
      crashed) is an infra failure: ci serve won't advance the pointer
      and will re-dispatch on the next poll.

Retry model:

  ci serve is fire-and-forget: enqueue three ignites per new sha,
  advance /ci/last_sha immediately, never wait. Gorn owns delivery
  and retry from there. GUIDs are deterministic ci-<tier-slug>-<sha>
  so a re-enqueue of the same (tier, sha) — e.g. after a ci serve
  crash + re-election — is a no-op against gorn's S3 idempotency.

  ci check's exit code drives gorn's task classification: exit 0
  → success, non-zero → non-retriable completed failure (infra).
  Transport-level crashes (ssh dead, wrap OOM'd) are retriable by
  gorn automatically — we don't model that here.
"""

import os
import random
import re
import shutil
import subprocess
import sys
import time


GIT_URL = 'https://github.com/pg83/ix'
ETCD_KEY_LAST_SHA = '/ci/last_sha'
POLL_INTERVAL_S = 10
TIERS = ['set/ci/tier/0', 'set/ci/tier/1', 'set/ci/tier/2']

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


def etcd_get(key):
    res = subprocess.run(
        ('etcdctl', 'get', '--print-value-only', key),
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )

    return res.stdout.strip()


def etcd_put(key, value):
    subprocess.run(('etcdctl', 'put', key, value), check=True)


def guid_for(tier, sha):
    return f'ci-{tier.replace("/", "_")}-{sha}'


# Env names propagated to the ci-check worker. Molot on the worker side
# reads the same names, so ./ix build inside ci check sees a correctly
# configured executor. Keep this list narrow: config + S3 credentials
# only, no runit internals.
FORWARD_ENV = [
    'GORN_API',
    'S3_ENDPOINT',
    'S3_BUCKET',
    'AWS_ACCESS_KEY_ID',
    'AWS_SECRET_ACCESS_KEY',
    'MOLOT_FULL_SLOTS',
    'MOLOT_QUIET',
]


def ignite(tier, sha):
    args = [
        'gorn', 'ignite',
        '--guid', guid_for(tier, sha),
        '--descr', f'ci check {tier} {sha}',
    ]

    for k in FORWARD_ENV:
        v = os.environ.get(k)

        if v is not None:
            args += ['--env', f'{k}={v}']

    args += ['--', 'ci', 'check', tier, sha]

    # stdin=DEVNULL — ignite's `-- argv` mode reads stdin to embed as
    # the inner cmd's stdin. Inheriting runit's stdin would block.
    # No --wait: ignite returns as soon as the task is accepted by
    # gorn control. ci serve never blocks on a running build.
    subprocess.run(args, stdin=subprocess.DEVNULL, check=True)


def serve():
    while True:
        remote = git_ls_remote_head(GIT_URL)
        last = etcd_get(ETCD_KEY_LAST_SHA)

        if remote == last:
            time.sleep(POLL_INTERVAL_S)
            continue

        log(f'new sha: {last or "<empty>"} -> {remote}; enqueuing {len(TIERS)} tiers')

        for tier in TIERS:
            ignite(tier, remote)

        etcd_put(ETCD_KEY_LAST_SHA, remote)
        log(f'advanced last_sha -> {remote}')


def has_target_fail(blob):
    return any(p.search(blob) for p in TARGET_FAIL_PATTERNS)


def check(tier, sha):
    workdir = f'/tmp/ci-work-{os.getpid()}'

    if os.path.exists(workdir):
        shutil.rmtree(workdir)

    os.makedirs(workdir)

    subprocess.run(('git', 'clone', GIT_URL, workdir), check=True)
    subprocess.run(('git', '-C', workdir, 'checkout', sha), check=True)

    # Sweep stale mc-molot-<N> workdirs before the build — molot
    # leaves them behind when owning processes die without cleanup
    # (same sweep the old ci_cycle.sh did).
    for name in os.listdir(workdir):
        if name.startswith('mc-molot-'):
            shutil.rmtree(os.path.join(workdir, name))

    env = os.environ.copy()
    env['IX_EXEC_KIND'] = 'molot'
    env.setdefault('S3_BUCKET', 'gorn')
    env['MOLOT_CACHE'] = './cache'

    # start_new_session=True: ./ix build's execute.py does
    # `os.kill(0, SIGKILL)` on target-subprocess failure, which kills
    # its entire process group. Without a new session, that group
    # includes us — we'd be dead before we could classify the failure.
    proc = subprocess.Popen(
        ('./ix', 'build', tier, '--seed=1'),
        cwd=workdir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    chunks = []

    while True:
        c = proc.stdout.read(65536)

        if not c:
            break

        chunks.append(c)
        # Tee to stderr so the build log is live in gorn wrap's
        # captured stderr (visible via `gorn control` API).
        os.write(2, c)

    rc = proc.wait()
    blob = b''.join(chunks)

    if rc == 0:
        log('ix build succeeded')
        sys.exit(0)

    if has_target_fail(blob):
        log(f'ix build exited {rc} with target-failure marker — counted as build error (ci check success)')
        sys.exit(0)

    log(f'ix build exited {rc} with no target-failure marker — infra error')
    sys.exit(rc if rc else 2)


def main():
    if len(sys.argv) < 2:
        print('usage: ci {serve | check <tier> <sha>}', file=sys.stderr)
        sys.exit(2)

    cmd = sys.argv[1]

    if cmd == 'serve':
        # Stagger lock-acquisition attempts across hosts so a deploy
        # doesn't dogpile etcd (same dance as SamogonBot / MirrorFetch).
        # Only matters the first time — after the leader is established,
        # peers block inside etcdctl.
        time.sleep(random.random() * 10)
        serve()
        return

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
