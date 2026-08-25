#!/usr/bin/env python3

"""
One autonomous IX CI repair cycle.

The cluster scheduler starts this command asynchronously through gorn and
holds /lock/updater/fixer/work around the complete process.  The worker:

  1. clones pg83/ix at main;
  2. seeds Molot's durable success cache from cix/complete;
  3. runs ``./ix build set/ci/tier/0 --seed=1`` through Molot, deliberately
     without a keep-going flag, and stops its process group at the first
     direct ``node failed:`` marker;
  4. exits when the build is green;
  5. on a real target failure, invokes one non-interactive Codex agent and
     gives it the checkout plus the complete log.

Infrastructure failures do not spend an agent run.  The next cron cycle will
retry them.  The lab's bin/codex/wrap package forces Codex and every command it
spawns through Wirez.  Authentication is loaded just in time from the
host-only secret service and materialized as CODEX_HOME/auth.json only inside
this worker's temporary directory.  Codex may rotate its refresh token, so the
updated file is always written back before the temporary directory disappears.
Repository credentials are not present while the agent runs: the supervisor
fetches /github/token only after Codex exits, validates the agent's local
commit, and publishes that exact commit without rewriting it.
"""

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


IX_GIT_URL = 'https://github.com/pg83/ix.git'
IX_BRANCH = 'main'
IX_TARGET = 'set/ci/tier/0'
FIXER_GENERATION = '5'
CODEX_MODEL = 'gpt-5.6-sol'
CODEX_REASONING_EFFORT = 'xhigh'
GIT_TOKEN_URL = 'http://127.0.0.1:8022/github/token'
CODEX_AUTH_URL = 'http://127.0.0.1:8022/codex/auth'
CODEX_AUTH_KEY_URL = 'http://127.0.0.1:8022/codex/auth/key'
CODEX_AUTH_MAX_BYTES = 1024 * 1024
CODEX_AUTH_ETCD_KEY = '/updater/fixer/codex-auth'
CODEX_AUTH_ENVELOPE_VERSION = 1
CODEX_AUTH_ENVELOPE_ALGORITHM = 'aes-256-cbc+hmac-sha256'
CODEX_AUTH_HKDF_INFO = b'ix-updater-fixer/codex-auth/v1'
CODEX_AUTH_AES = '-aes-256-cbc'

CACHE_LOCK_KEY = '/lock/ci/cache'
CACHE_S3_BUCKET = 'cix'
CACHE_S3_KEY = 'complete'
MC_ALIAS = 'fixer_cache'

ANSI_RE = re.compile(rb'\x1b\[[0-9;?]*[ -/]*[@-~]')
DIRECT_FAIL_MARKER = b'node failed: '
BUILD_STOP_TIMEOUT_S = 10
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
        'ETCD_PERSIST_ENDPOINTS',
        'GIT_USER',
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
        ('etcd_lock', CACHE_LOCK_KEY, '--',
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


def fetch_secret(url, description, limit=CODEX_AUTH_MAX_BYTES):
    log(f'load {description} from {url}')

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            value = resp.read(limit + 1)
    except Exception as exc:
        raise InfrastructureFailure(f'cannot load {description}') from exc

    if not value:
        raise InfrastructureFailure(f'{description} is empty')

    if len(value) > limit:
        raise InfrastructureFailure(f'{description} is too large')

    return value


def validate_codex_auth(auth):
    if len(auth) > CODEX_AUTH_MAX_BYTES:
        raise InfrastructureFailure('CODEX auth is too large')

    try:
        parsed = json.loads(auth)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InfrastructureFailure('invalid CODEX auth') from exc

    if not isinstance(parsed, dict):
        raise InfrastructureFailure('CODEX auth is not a JSON object')

    return auth


def load_codex_wrapping_key(env):
    url = env.get('IX_FIXER_CODEX_AUTH_KEY_URL', CODEX_AUTH_KEY_URL)
    raw = fetch_secret(url, 'CODEX auth wrapping key', limit=256).strip()

    try:
        key = bytes.fromhex(raw.decode())
    except (UnicodeDecodeError, ValueError) as exc:
        raise InfrastructureFailure(
            'CODEX auth wrapping key must be 64 hexadecimal characters'
        ) from exc

    if len(key) != 32:
        raise InfrastructureFailure(
            'CODEX auth wrapping key must be 64 hexadecimal characters'
        )

    return key


def load_codex_bootstrap(env):
    url = env.get('IX_FIXER_CODEX_AUTH_URL', CODEX_AUTH_URL)
    return validate_codex_auth(fetch_secret(url, 'CODEX auth'))


def hkdf_sha256(secret, salt, info, length):
    """RFC 5869 HKDF-SHA256 extract+expand."""
    prk = hmac.new(salt, secret, hashlib.sha256).digest()
    out = b''
    block = b''
    counter = 1

    while len(out) < length:
        block = hmac.new(
            prk,
            block + info + bytes((counter,)),
            hashlib.sha256,
        ).digest()
        out += block
        counter += 1

    return out[:length]


def codex_auth_keys(wrapping_key, salt):
    material = hkdf_sha256(
        wrapping_key,
        salt,
        CODEX_AUTH_HKDF_INFO,
        64,
    )
    return material[:32], material[32:]


def codex_auth_mac_input(seed_hash, salt, iv, ciphertext):
    return (
        b'ix-updater-fixer-codex-auth-v1\0'
        + seed_hash.encode()
        + salt
        + iv
        + ciphertext
    )


def encrypt_codex_auth(auth, wrapping_key, seed_hash):
    validate_codex_auth(auth)
    salt = os.urandom(32)
    iv = os.urandom(16)
    encryption_key, mac_key = codex_auth_keys(wrapping_key, salt)
    ciphertext = subprocess.check_output(
        (
            'openssl', 'enc', CODEX_AUTH_AES,
            '-K', encryption_key.hex(),
            '-iv', iv.hex(),
        ),
        input=auth,
    )
    tag = hmac.new(
        mac_key,
        codex_auth_mac_input(seed_hash, salt, iv, ciphertext),
        hashlib.sha256,
    ).digest()
    envelope = {
        'alg': CODEX_AUTH_ENVELOPE_ALGORITHM,
        'ct': base64.b64encode(ciphertext).decode(),
        'iv': base64.b64encode(iv).decode(),
        'key': hashlib.sha256(wrapping_key).hexdigest(),
        'salt': base64.b64encode(salt).decode(),
        'seed': seed_hash,
        'tag': base64.b64encode(tag).decode(),
        'v': CODEX_AUTH_ENVELOPE_VERSION,
    }
    return (json.dumps(envelope, separators=(',', ':'), sort_keys=True) + '\n').encode()


def decrypt_codex_auth(raw, wrapping_key):
    try:
        envelope = json.loads(raw)

        if envelope['v'] != CODEX_AUTH_ENVELOPE_VERSION:
            raise ValueError('unsupported version')

        if envelope['alg'] != CODEX_AUTH_ENVELOPE_ALGORITHM:
            raise ValueError('unsupported algorithm')

        seed_hash = envelope['seed']

        if not re.fullmatch(r'[0-9a-f]{64}', seed_hash):
            raise ValueError('invalid seed fingerprint')

        if envelope['key'] != hashlib.sha256(wrapping_key).hexdigest():
            return None, None

        salt = base64.b64decode(envelope['salt'], validate=True)
        iv = base64.b64decode(envelope['iv'], validate=True)
        ciphertext = base64.b64decode(envelope['ct'], validate=True)
        tag = base64.b64decode(envelope['tag'], validate=True)
    except (KeyError, TypeError, binascii.Error, json.JSONDecodeError, ValueError) as exc:
        raise InfrastructureFailure('invalid encrypted CODEX auth in etcd') from exc

    if len(salt) != 32 or len(iv) != 16 or len(tag) != hashlib.sha256().digest_size:
        raise InfrastructureFailure('invalid encrypted CODEX auth sizes in etcd')

    encryption_key, mac_key = codex_auth_keys(wrapping_key, salt)
    expected = hmac.new(
        mac_key,
        codex_auth_mac_input(seed_hash, salt, iv, ciphertext),
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(tag, expected):
        raise InfrastructureFailure('encrypted CODEX auth authentication failed')

    try:
        auth = subprocess.check_output(
            (
                'openssl', 'enc', CODEX_AUTH_AES,
                '-K', encryption_key.hex(),
                '-iv', iv.hex(),
                '-d',
            ),
            input=ciphertext,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        raise InfrastructureFailure('cannot decrypt CODEX auth from etcd') from exc

    return validate_codex_auth(auth), seed_hash


def read_codex_auth_etcd(env):
    etcd_env = dict(env)
    etcd_env['ETCDCTL_ENDPOINTS'] = env['ETCD_PERSIST_ENDPOINTS']
    result = subprocess.run(
        ('etcdctl', 'get', '--print-value-only', CODEX_AUTH_ETCD_KEY),
        env=etcd_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if result.returncode != 0:
        sys.stderr.buffer.write(result.stderr)
        raise InfrastructureFailure('cannot load encrypted CODEX auth from etcd')

    return result.stdout


def load_codex_auth(env):
    wrapping_key = load_codex_wrapping_key(env)
    bootstrap = load_codex_bootstrap(env)
    seed_hash = hashlib.sha256(bootstrap).hexdigest()
    encrypted = read_codex_auth_etcd(env)

    if not encrypted:
        log('no runtime CODEX auth in etcd; use encrypted-store bootstrap')
        return bootstrap, wrapping_key, seed_hash

    auth, saved_seed_hash = decrypt_codex_auth(encrypted, wrapping_key)

    if auth is None:
        log('CODEX wrapping key changed; use encrypted-store bootstrap')
        return bootstrap, wrapping_key, seed_hash

    if saved_seed_hash != seed_hash:
        log('CODEX auth bootstrap changed; replace stale runtime state')
        return bootstrap, wrapping_key, seed_hash

    return auth, wrapping_key, seed_hash


def save_codex_auth(auth, wrapping_key, seed_hash, env):
    encrypted = encrypt_codex_auth(auth, wrapping_key, seed_hash)
    log(f'save refreshed CODEX auth to etcd {CODEX_AUTH_ETCD_KEY}')
    etcd_env = dict(env)
    etcd_env['ETCDCTL_ENDPOINTS'] = env['ETCD_PERSIST_ENDPOINTS']
    result = subprocess.run(
        ('etcdctl', 'put', CODEX_AUTH_ETCD_KEY),
        env=etcd_env,
        input=encrypted,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if result.returncode != 0:
        sys.stderr.buffer.write(result.stderr)
        raise InfrastructureFailure('cannot save encrypted CODEX auth to etcd')


def molot_env(base_env, cache_path):
    env = dict(base_env)
    # Molot needs its own S3 credentials.  Codex auth never crosses the task
    # environment; it is loaded from the host-only secret service just in time.
    env.pop('CODEX_AUTH_B64', None)  # Do not leak payloads from obsolete tasks.
    env['IX_EXEC_KIND'] = 'molot'
    env['AWS_ACCESS_KEY_ID'] = base_env['AWS_ACCESS_KEY_ID_MOLOT']
    env['AWS_SECRET_ACCESS_KEY'] = base_env['AWS_SECRET_ACCESS_KEY_MOLOT']
    env['S3_BUCKET'] = 'molot'
    env['MOLOT_CACHE'] = str(cache_path.resolve())
    return env


def materialize_codex_home(work, auth):
    auth = validate_codex_auth(auth)
    home = work / 'codex-home'
    home.mkdir(mode=0o700)
    auth_path = home / 'auth.json'
    auth_path.write_bytes(auth)
    auth_path.chmod(0o600)

    # A login shell sources /etc/profile and overwrites the supervisor's
    # IX_EXEC_KIND=molot with IX_EXEC_KIND=system.  Keep agent commands in a
    # regular shell and let them inherit the supervisor's curated environment,
    # including Molot's endpoints/cache.  Repository credentials and the auth
    # payload have already been removed.
    config_path = home / 'config.toml'
    config_path.write_text(
        'allow_login_shell = false\n'
        '\n'
        '[shell_environment_policy]\n'
        'inherit = "all"\n'
    )
    config_path.chmod(0o600)
    return home


def codex_agent_env(base_env, cache_path, codex_home):
    env = molot_env(base_env, cache_path)
    # The supervisor needs persistent etcd for auth state.  The repair agent
    # only needs Molot/Gorn and must not receive the durable etcd endpoint.
    env.pop('ETCD_PERSIST_ENDPOINTS', None)
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


def stop_build_process_group(proc):
    """Stop the isolated IX/Molot process group and return its status."""
    if proc.poll() is not None:
        return proc.returncode

    log(f'stop build process group {proc.pid} after first direct failure')

    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    try:
        return proc.wait(timeout=BUILD_STOP_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        log(f'build process group {proc.pid} ignored SIGTERM; sending SIGKILL')

        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

        return proc.wait()


def run_build(repo, cache_path, env):
    target = IX_TARGET
    build_log = repo / '.fixer-build.log'
    cmd = ('./ix', 'build', target, '--seed=1')
    log('run', *cmd, '(molot, no -k)')

    proc = subprocess.Popen(
        cmd,
        cwd=repo,
        env=molot_env(env, cache_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    returncode = None

    try:
        with build_log.open('wb') as out:
            for line in proc.stdout:
                out.write(line)
                out.flush()

                clean = ANSI_RE.sub(b'', line)

                if DIRECT_FAIL_MARKER in clean:
                    returncode = stop_build_process_group(proc)
                    break

        if returncode is None:
            returncode = proc.wait()
    except BaseException:
        stop_build_process_group(proc)
        raise
    finally:
        proc.stdout.close()

    stream_file(build_log, sys.stderr.buffer)
    sys.stderr.flush()
    return returncode, build_log


def codex_prompt(target, revision, summary):
    return f"""You are the autonomous repair worker for the IX package repository.

Repository HEAD before this attempt: {revision}
Reproduce the failure with:

    ./ix build {target} --seed=1

It was intentionally run without -k and the probe was stopped immediately
after its first direct `node failed:` marker.  Its complete combined output up
to that marker is in `.fixer-build.log`, which is locally ignored by git.
Initial direct failure markers are:

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
3. Validate the affected package with `./ix build <package> --seed=1`.  Run
   that command directly, without a pipeline that can hide its exit status.
   A zero exit status from the validation build is mandatory.
   If validation cannot execute or exits nonzero, do not commit.  Restore the
   clean checkout and stop.
4. If the failure is transient infrastructure trouble and needs no repository
   change, leave the tree clean and stop.
5. Otherwise create exactly one local commit directly on top of `{revision}`.
   Use a concise factual commit message that names the package or shared logic
   and describes the actual fix.  Leave the working tree clean.
6. Do not fetch, rebase, push, amend or rewrite existing commits, or change git
   remotes and configuration.  Repository credentials are intentionally absent.

This is an unattended repair job.  Complete the diagnosis, edit, and
validation without asking for interactive input.  You own the single local
repair commit; the supervisor exclusively owns remote publication.
"""


def codex_command(repo, prompt):
    return (
        'timeout', '3600', 'codex', 'exec',
        '--model', CODEX_MODEL,
        '--config', f'model_reasoning_effort="{CODEX_REASONING_EFFORT}"',
        '--dangerously-bypass-approvals-and-sandbox',
        '--ephemeral',
        '--color', 'never',
        '-C', str(repo),
        prompt,
    )


def run_codex(repo, cache_path, build_log, env):
    target = IX_TARGET
    revision = subprocess.check_output(
        ('git', 'rev-parse', 'HEAD'), cwd=repo, text=True,
    ).strip()
    prompt = codex_prompt(target, revision, failure_summary(build_log))
    auth, wrapping_key, seed_hash = load_codex_auth(env)
    codex_home = materialize_codex_home(repo.parent, auth)
    agent_env = codex_agent_env(env, cache_path, codex_home)
    cmd = codex_command(repo, prompt)
    log(f'run codex target={target}')

    try:
        subprocess.run(cmd, cwd=repo, env=agent_env, check=True)
    finally:
        # Persist rotations even on a non-zero Codex exit or timeout.  Losing
        # an updated auth.json here would leave the saved refresh token stale.
        save_codex_auth(
            (codex_home / 'auth.json').read_bytes(),
            wrapping_key,
            seed_hash,
            env,
        )

    return revision


def git_output(repo, *args):
    return subprocess.check_output(
        ('git', *args),
        cwd=repo,
        text=True,
    ).strip()


def validate_agent_commit(repo, revision):
    """Return the one clean agent commit, or None for a clean no-op."""
    head = git_output(repo, 'rev-parse', 'HEAD')
    status = git_output(repo, 'status', '--porcelain=v1', '--untracked-files=all')

    if head == revision:
        if status:
            raise InfrastructureFailure(
                'Codex left uncommitted repository changes; refusing to publish'
            )

        log('Codex left no repository change; nothing to publish')
        return None

    if status:
        raise InfrastructureFailure(
            'Codex committed with a dirty working tree; refusing to publish'
        )

    commit_line = git_output(repo, 'rev-list', '--parents', '-n', '1', head).split()

    if len(commit_line) != 2 or commit_line[1] != revision:
        raise InfrastructureFailure(
            'Codex did not leave exactly one commit on the original HEAD'
        )

    subject = git_output(repo, 'log', '-1', '--format=%s', head)

    if not subject or len(subject) > 120:
        raise InfrastructureFailure('Codex left an invalid commit subject')

    changed = git_output(
        repo,
        'diff-tree', '--no-commit-id', '--name-only', '-r', head,
    ).splitlines()
    forbidden = {'.fixer-build.log', '.fixer-molot-cache'}

    if not changed:
        raise InfrastructureFailure('Codex left an empty repair commit')

    if forbidden.intersection(changed):
        raise InfrastructureFailure('Codex committed fixer scratch files')

    subprocess.run(
        ('git', 'diff', '--check', revision, head),
        cwd=repo,
        check=True,
    )
    log(f'validated Codex commit {head[:12]}: {subject}')
    return head


def publish_fix(repo, revision, branch, env):
    """Validate and push the agent's exact commit under supervisor auth."""
    head = validate_agent_commit(repo, revision)

    if head is None:
        return False

    git_url = env.get('IX_FIXER_GIT_URL', IX_GIT_URL)
    subprocess.run(
        ('git', 'fetch', git_url, branch),
        cwd=repo,
        env=git_read_env(env),
        check=True,
    )
    remote_head = git_output(repo, 'rev-parse', 'FETCH_HEAD')

    if remote_head != revision:
        log(
            f'origin {branch} moved from {revision[:12]} to '
            f'{remote_head[:12]}; discard agent checkout and retry next cycle'
        )
        return False

    token = load_repo_token(env)
    subprocess.run(
        (
            'git',
            '-c', 'core.hooksPath=/dev/null',
            '-c', 'credential.helper=',
            'push', git_url, f'{head}:refs/heads/{branch}',
        ),
        cwd=repo,
        env=git_push_env(env, token),
        check=True,
    )
    log(f'published Codex commit {head[:12]} to {branch}')
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
            # not just the initial set/ci/tier/0 probe.
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
