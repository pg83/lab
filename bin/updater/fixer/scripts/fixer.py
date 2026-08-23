#!/usr/bin/env python3

"""
One autonomous IX CI repair cycle.

The cluster scheduler starts this command asynchronously through gorn and
holds /lock/updater/fixer/work around the complete process.  The worker:

  1. clones pg83/ix at main;
  2. seeds Molot's durable success cache from cix/complete;
  3. runs ``./ix build set/ci --seed=1`` through Molot, deliberately without
     a keep-going flag;
  4. exits when the build is green;
  5. on a real target failure, invokes one non-interactive Codex agent and
     gives it the checkout plus the complete log.

Infrastructure failures do not spend an agent run.  The next cron cycle will
retry them.  The lab's bin/codex/wrap package forces Codex and every command it
spawns through Wirez.  Authentication comes from the encrypted lab secret at
/codex/auth and is materialized as CODEX_HOME/auth.json only inside this
worker's temporary directory.  Repository credentials are not present while
the agent runs: the supervisor fetches /github/token from the host-only secret
service only after Codex exits, then commits and publishes the prepared tree.
"""

import base64
import binascii
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


IX_GIT_URL = 'https://github.com/pg83/ix.git'
IX_BRANCH = 'main'
IX_TARGET = 'set/ci'
FIXER_GENERATION = '2'
GIT_TOKEN_URL = 'http://127.0.0.1:8022/github/token'

CACHE_LOCK_KEY = '/lock/ci/cache'
CACHE_S3_BUCKET = 'cix'
CACHE_S3_KEY = 'complete'
MC_ALIAS = 'fixer_cache'

ANSI_RE = re.compile(rb'\x1b\[[0-9;?]*[ -/]*[@-~]')
TARGET_FAIL_MARKERS = (
    b'ERROR ',
    b'node failed: ',
    b'---- stdout of failed node ',
    b'---- stderr of failed node ',
    b'failed via gorn ignite',
)


class InfrastructureFailure(Exception):
    """The build did not reach a package failure; retry without Codex."""


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def require_env(env):
    required = (
        'GORN_API',
        'S3_ENDPOINT',
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_ACCESS_KEY_ID_MOLOT',
        'AWS_SECRET_ACCESS_KEY_MOLOT',
        'ETCDCTL_ENDPOINTS',
        'GIT_USER',
        'CODEX_AUTH_B64',
        'IX_FIXER_CODEX_GORN_API',
        'IX_FIXER_CODEX_S3_ENDPOINT',
        'IX_FIXER_GENERATION',
    )
    missing = [name for name in required if not env.get(name)]

    if missing:
        raise InfrastructureFailure('missing required environment: ' + ', '.join(missing))

    if env['IX_FIXER_GENERATION'] != FIXER_GENERATION:
        raise InfrastructureFailure('obsolete fixer generation')


def mc_env(base_env):
    scheme, host = base_env['S3_ENDPOINT'].split('://', 1)
    key = base_env['AWS_ACCESS_KEY_ID']
    secret = base_env['AWS_SECRET_ACCESS_KEY']
    env = dict(base_env)
    env[f'MC_HOST_{MC_ALIAS}'] = f'{scheme}://{key}:{secret}@{host}'
    return env


def cache_uri():
    return f'{MC_ALIAS}/{CACHE_S3_BUCKET}/{CACHE_S3_KEY}'


def seed_cache(path, env):
    log(f'seed Molot cache {path}')
    res = subprocess.run(
        ('minio-client', 'cat', cache_uri()),
        env=mc_env(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if res.returncode == 0:
        path.write_bytes(res.stdout)
        return

    if b'Object does not exist' in res.stderr or b'NoSuchKey' in res.stderr:
        path.write_bytes(b'')
        return

    sys.stderr.buffer.write(res.stderr)
    res.check_returncode()


def merge_cache(path, env):
    log(f'merge Molot cache {path}')
    subprocess.run(
        ('etcdctl', 'lock', CACHE_LOCK_KEY, '--',
         'updater', 'cache-update', str(path)),
        env=env,
        check=True,
    )


def clone_ix(dst, env):
    git_url = env.get('IX_FIXER_GIT_URL', IX_GIT_URL)
    branch = env.get('IX_FIXER_BRANCH', IX_BRANCH)
    log(f'clone {git_url} branch={branch}')

    subprocess.run(
        ('git', 'clone', '--single-branch', '--branch', branch, git_url, str(dst)),
        env=git_read_env(env),
        check=True,
    )
    subprocess.run(('git', 'config', 'user.name', 'ix fixer'), cwd=dst, check=True)
    subprocess.run(
        ('git', 'config', 'user.email', 'ix-fixer@users.noreply.github.com'),
        cwd=dst,
        check=True,
    )

    # The agent must be able to inspect the complete log and update Molot's
    # cache without ever adding either scratch file to a commit.
    exclude = dst / '.git' / 'info' / 'exclude'

    with exclude.open('a') as out:
        out.write('\n/.fixer-build.log\n/.fixer-molot-cache\n')

    return branch


def git_read_env(base_env):
    """Return an environment which cannot authenticate writes to GitHub."""
    env = dict(base_env)

    for name in (
        'GIT_USER',
        'GIT_PASS',
        'GIT_ASKPASS',
        'SSH_ASKPASS',
        'SSH_AUTH_SOCK',
        'GH_TOKEN',
        'GITHUB_TOKEN',
    ):
        env.pop(name, None)

    env['GIT_TERMINAL_PROMPT'] = '0'
    return env


def git_push_env(base_env, token):
    env = dict(base_env)
    env['GIT_PASS'] = token
    env['GIT_ASKPASS'] = 'passenv'
    env['GIT_TERMINAL_PROMPT'] = '0'
    return env


def load_repo_token(env):
    url = env.get('IX_FIXER_GIT_TOKEN_URL', GIT_TOKEN_URL)
    log(f'load repository token from {url}')

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            token = resp.read().decode().strip()
    except Exception as exc:
        raise InfrastructureFailure('cannot load repository token') from exc

    if not token:
        raise InfrastructureFailure('repository token is empty')

    return token


def molot_env(base_env, cache_path):
    env = dict(base_env)
    # Molot needs its own S3 credentials, but never the Codex login payload.
    env.pop('CODEX_AUTH_B64', None)
    env['IX_EXEC_KIND'] = 'molot'
    env['AWS_ACCESS_KEY_ID'] = base_env['AWS_ACCESS_KEY_ID_MOLOT']
    env['AWS_SECRET_ACCESS_KEY'] = base_env['AWS_SECRET_ACCESS_KEY_MOLOT']
    env['S3_BUCKET'] = 'molot'
    env['MOLOT_CACHE'] = str(cache_path.resolve())
    return env


def materialize_codex_home(work, env):
    try:
        auth = base64.b64decode(env['CODEX_AUTH_B64'], validate=True)
        json.loads(auth)
    except (KeyError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InfrastructureFailure('invalid CODEX auth from /codex/auth') from exc

    home = work / 'codex-home'
    home.mkdir(mode=0o700)
    auth_path = home / 'auth.json'
    auth_path.write_bytes(auth)
    auth_path.chmod(0o600)
    return home


def codex_agent_env(base_env, cache_path, codex_home):
    env = molot_env(base_env, cache_path)
    # The agent runs in Wirez's network namespace.  Host-loopback endpoints
    # are unreachable there, so use the cluster-facing 192.* listeners which
    # the codex wrapper explicitly bypasses around SOCKS.
    env['GORN_API'] = base_env['IX_FIXER_CODEX_GORN_API']
    env['S3_ENDPOINT'] = base_env['IX_FIXER_CODEX_S3_ENDPOINT']
    env['CODEX_HOME'] = str(codex_home)
    return git_read_env(env)


def stream_file(path, out):
    with path.open('rb') as src:
        shutil.copyfileobj(src, out, length=1024 * 1024)


def has_target_failure(path):
    with path.open('rb') as src:
        for line in src:
            clean = ANSI_RE.sub(b'', line)

            if any(marker in clean for marker in TARGET_FAIL_MARKERS):
                return True

    return False


def failure_summary(path, limit=12):
    lines = []

    with path.open('rb') as src:
        for line in src:
            clean = ANSI_RE.sub(b'', line).strip()

            if any(marker in clean for marker in TARGET_FAIL_MARKERS):
                lines.append(clean.decode(errors='replace'))

                if len(lines) == limit:
                    break

    return '\n'.join(lines)


def run_build(repo, cache_path, env):
    target = env.get('IX_FIXER_TARGET', IX_TARGET)
    build_log = repo / '.fixer-build.log'
    cmd = ('./ix', 'build', target, '--seed=1')
    log('run', *cmd, '(molot, no -k)')

    with build_log.open('wb') as out:
        res = subprocess.run(
            cmd,
            cwd=repo,
            env=molot_env(env, cache_path),
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            check=False,
        )

    stream_file(build_log, sys.stderr.buffer)
    sys.stderr.flush()
    return res.returncode, build_log


def codex_prompt(target, revision, summary):
    return f"""You are the autonomous repair worker for the IX package repository.

Repository HEAD before this attempt: {revision}
Reproduce the failure with:

    ./ix build {target} --seed=1

It was intentionally run without -k.  Its complete combined output is in
`.fixer-build.log`, which is locally ignored by git.  Initial direct failure
markers are:

{summary or '(inspect .fixer-build.log)'}

Perform one repair cycle:

1. Inspect `.fixer-build.log`.  Find the first direct failed node and its root
   cause; ignore nodes reported only as `BROKEN BY DEP`.
2. Fix that package or shared build logic with the smallest correct change.
   Do not perform mechanical version upgrades and do not edit the build log.
   If an updated dependency caused the failure, use this preference order:
   a. Fix the updated dependency itself so every consumer benefits.
   b. If the dependency is correct and only one consumer is incompatible, fix
      that broken consumer.
   c. Revert the dependency update only as a last resort.  When reverting it,
      add the `noauto` marker to its recipe so the updater cannot immediately
      apply the same broken update again.
3. Validate the affected package with `./ix build <package> --seed=1`.
4. If the failure is transient infrastructure trouble and needs no repository
   change, leave the tree clean and stop.
5. Otherwise leave the tested fix in the working tree for the supervisor.
   Do not commit, fetch, rebase, push, or change git remotes and configuration.

This is an unattended repair job.  Complete the diagnosis, edit, and
validation without asking for interactive input.  The supervisor exclusively
owns git history and publication.
"""


def codex_command(repo, prompt):
    return (
        'timeout', '3600', 'codex', 'exec',
        '--dangerously-bypass-approvals-and-sandbox',
        '--ephemeral',
        '--color', 'never',
        '-C', str(repo),
        prompt,
    )


def run_codex(repo, cache_path, build_log, env):
    target = env.get('IX_FIXER_TARGET', IX_TARGET)
    revision = subprocess.check_output(
        ('git', 'rev-parse', 'HEAD'), cwd=repo, text=True,
    ).strip()
    prompt = codex_prompt(target, revision, failure_summary(build_log))
    codex_home = materialize_codex_home(repo.parent, env)
    agent_env = codex_agent_env(env, cache_path, codex_home)
    cmd = codex_command(repo, prompt)
    log(f'run codex target={target}')
    subprocess.run(cmd, cwd=repo, env=agent_env, check=True)
    return revision


def publish_fix(repo, revision, branch, env):
    """Commit and push an agent-prepared working tree under supervisor auth."""
    head = subprocess.check_output(
        ('git', 'rev-parse', 'HEAD'), cwd=repo, text=True,
    ).strip()

    if head != revision:
        raise InfrastructureFailure('Codex changed git history; refusing to publish')

    subprocess.run(('git', 'add', '-A'), cwd=repo, check=True)
    clean = subprocess.run(
        ('git', 'diff', '--cached', '--quiet'), cwd=repo, check=False,
    )

    if clean.returncode == 0:
        log('Codex left no repository change; nothing to publish')
        return False

    if clean.returncode != 1:
        raise InfrastructureFailure(f'git diff --cached failed with {clean.returncode}')

    subprocess.run(('git', 'diff', '--cached', '--check'), cwd=repo, check=True)
    subprocess.run(
        ('git', 'commit', '-m', f'fix CI after {revision[:12]}'),
        cwd=repo,
        check=True,
    )

    git_url = env.get('IX_FIXER_GIT_URL', IX_GIT_URL)
    subprocess.run(('git', 'remote', 'set-url', 'origin', git_url), cwd=repo, check=True)
    subprocess.run(
        ('git', 'fetch', 'origin', branch),
        cwd=repo,
        env=git_read_env(env),
        check=True,
    )
    subprocess.run(('git', 'rebase', f'origin/{branch}'), cwd=repo, check=True)
    token = load_repo_token(env)
    subprocess.run(
        ('git', 'push', 'origin', f'HEAD:refs/heads/{branch}'),
        cwd=repo,
        env=git_push_env(env, token),
        check=True,
    )
    log(f'published Codex fix to {branch}')
    return True


def run_fixer(env):
    require_env(env)

    with tempfile.TemporaryDirectory(prefix='updater-fixer.', dir=os.getcwd()) as work:
        work = Path(work).resolve()
        repo = work / 'ix'
        branch = clone_ix(repo, env)
        cache_path = repo / '.fixer-molot-cache'
        seed_cache(cache_path, env)

        try:
            returncode, build_log = run_build(repo, cache_path, env)

            if returncode == 0:
                log('IX CI build is green; no agent needed')
                return

            if not has_target_failure(build_log):
                raise InfrastructureFailure(
                    f'ix build exited {returncode} without a target-failure marker'
                )

            log(f'IX CI target failed (exit {returncode}); starting one Codex repair')
            revision = run_codex(repo, cache_path, build_log, env)
            publish_fix(repo, revision, branch, env)
        finally:
            # Include cache entries produced by Codex's targeted validation,
            # not just the initial set/ci probe.
            merge_cache(cache_path, env)


def usage():
    print('usage: updater_fixer run', file=sys.stderr)
    raise SystemExit(2)


def main():
    if sys.argv[1:] != ['run']:
        usage()

    run_fixer(os.environ.copy())


if __name__ == '__main__':
    main()
