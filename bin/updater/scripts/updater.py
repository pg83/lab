#!/usr/bin/env python3

"""
Automated IX package updater.

The long-running ``run`` command is launched by job_scheduler through a
fire-and-forget gorn task.  It copies the discovery and package-rewrite
semantics of IX's bin/ix/tools/upver, but every build is executed by Molot:

  1. Fetch Repology's stale-package list and apply the original skip list.
  2. Build the current package before touching its recipe.  A package build
     failure skips only that candidate.
  3. Replace exactly one recipe's old version and checksum (with a fresh
     invalid probe), preserving the original redirect, noauto, Go and Cargo
     rules.
  4. Build again, extract the checksum reported by IX/Molot, and write it.
  5. Commit and push immediately.  Deliberately do not run a third build;
     CI and the repair agent own failures after the mechanical update.

Molot's success cache is seeded from and merged into s3://cix/complete, the
same durable cache used by CI.  ``cache-update`` is the small helper invoked
under the shared /lock/ci/cache etcd_lock for the read-modify-write step.
"""

import json
import os
import re
import secrets
import ssl
import subprocess
import sys
import tempfile
import urllib.request
import urllib.parse
from dataclasses import dataclass
from pathlib import Path


REPOLOGY_URL = 'https://repology.org/api/v1/projects/?inrepo=stalix_dev&outdated=1'
IX_GIT_URL = 'https://github.com/pg83/ix.git'
IX_BRANCH = 'main'

CACHE_LOCK_KEY = '/lock/ci/cache'
CACHE_S3_BUCKET = 'cix'
CACHE_S3_KEY = 'complete'
MC_ALIAS = 'updater_cache'

GOOD_SHA_CHARS = frozenset('0123456789abcdef')
BUILD_FLAGS = ('--opengl=fake', '--vulkan=fake', '--seed=1')
REPOLOGY_PAGE_SIZE = 200

GO_LATEST = 26
GO_TOOL = (
    '\n' + chr(123) + '% block go_tool %}\n'
    f'bin/go/lang/{GO_LATEST}\n'
    + chr(123) + '% endblock %}\n'
)

CARGO_LATEST = 96
CARGO_TOOL = (
    '\n' + chr(123) + '% block cargo_tool %}\n'
    f'bld/cargo/{CARGO_LATEST}\n'
    + chr(123) + '% endblock %}\n'
)

ATTR_SNAPSHOT_URL = (
    'https://git.savannah.nongnu.org/cgit/attr.git/snapshot/'
    'attr-{{self.version().strip()}}.tar.gz'
)
ATTR_RELEASE_URL = (
    'https://download.savannah.gnu.org/releases/attr/'
    'attr-{{self.version().strip()}}.tar.gz'
)

# This is the grep -v chain from IX's bin/ix/tools/upver/scripts/fix.
# Match against the complete "old new pkg..." line to preserve its exact
# (occasionally broad) semantics rather than reinterpret it as package paths.
SKIP_SUBSTRINGS = (
    'mesa',
    'bld/',
    'lib/qt',
    'meson',
    'musl',
    'python',
    'perl',
    'rio',
    'ruby',
    'firmware',
    'chromium',
    'protobuf',
    'spirv',
    'vulkan',
    'webkit',
    'wlroots',
    'coreutils',
    'auto/make',
    'bin/kernel',
    'bin/glslang/old',
    'lib/ffmpeg',
    'go/lang',
    'lib/fmt',
    'bin/mariadb',
    'dmidecode',
    'lib/lua',
    'grpc',
)

ANSI_RE = re.compile(rb'\x1b\[[0-9;?]*[ -/]*[@-~]')


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


class CandidateFailure(Exception):
    """A package-specific failure: restore the recipe and continue."""


class InfrastructureFailure(Exception):
    """A run-wide failure: abort so the scheduler retries later."""


@dataclass(frozen=True)
class Candidate:
    old: str
    new: str
    packages: tuple

    @property
    def line(self):
        return ' '.join((self.old, self.new, *self.packages))


@dataclass(frozen=True)
class BuildResult:
    returncode: int
    output: bytes


def newest_version(records):
    for rec in records:
        if rec.get('status') == 'newest':
            return rec.get('version')

    return None


def our_version(records):
    for rec in records:
        if rec.get('repo') == 'stalix':
            return rec.get('version')

    return None


def our_packages(records):
    for rec in records:
        if rec.get('repo') == 'stalix' and rec.get('srcname'):
            yield rec['srcname']


def candidates_from_repology(data):
    for name in sorted(data):
        if 'unclassified' in name:
            log(f'skip {name}')
            continue

        records = data[name]
        old = our_version(records)
        new = newest_version(records)

        if not old or not new:
            continue

        candidate = Candidate(old, new, tuple(our_packages(records)))

        if any(part in candidate.line for part in SKIP_SUBSTRINGS):
            log(f'skip filtered {candidate.line}')
            continue

        yield candidate


def repology_page_url(url, bound):
    if not bound:
        return url

    parts = urllib.parse.urlsplit(url)
    path = parts.path.rstrip('/') + '/' + urllib.parse.quote(bound, safe='') + '/'
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def fetch_repology_page(url):
    log(f'fetch {url}')
    req = urllib.request.Request(url, headers={'User-Agent': 'ix-updater/1'})

    # The original updater intentionally used curl -k.  Stalix images do not
    # always carry a current CA bundle, so retain that network policy here.
    ctx = ssl._create_unverified_context()

    with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
        return json.load(resp)


def fetch_repology(url):
    result = {}
    bound = None

    while True:
        page = fetch_repology_page(repology_page_url(url, bound))
        result.update(page)

        if len(page) < REPOLOGY_PAGE_SIZE:
            break

        next_bound = max(page)

        if next_bound == bound:
            break

        bound = next_bound

    return result


def is_sha(value):
    return len(value) == 64 and all(ch in GOOD_SHA_CHARS for ch in value)


def recipe_sha(data):
    for line in data.split('\n'):
        for word in line.split(' '):
            if is_sha(word):
                return word

    raise CandidateFailure('recipe contains no standalone sha256')


def prepare_recipe(path, old, new, probe_sha):
    data = path.read_text()
    old_line = f'\n{old}\n'

    if 'noauto' in data or old_line not in data:
        return False

    updated = data.replace(recipe_sha(data), probe_sha).replace(old_line, f'\n{new}\n')
    updated = updated.replace(ATTR_SNAPSHOT_URL, ATTR_RELEASE_URL)

    if 'cargo_url' in updated:
        if 'cargo_tool' not in updated:
            updated += CARGO_TOOL

        for version in range(75, CARGO_LATEST):
            updated = updated.replace(f'bld/rust/{version}', f'bld/rust/{CARGO_LATEST}')
            updated = updated.replace(f'bld/cargo/{version}', f'bld/cargo/{CARGO_LATEST}')
    elif 'go_url' in updated:
        if 'go_tool' not in updated:
            updated += GO_TOOL

        for version in range(21, GO_LATEST):
            updated = updated.replace(f'bin/go/lang/{version}', f'bin/go/lang/{GO_LATEST}')

    path.write_text(updated)
    return True


def recipe_accepts_update(path, old):
    data = path.read_text()
    return 'noauto' not in data and f'\n{old}\n' in data


def install_sha(path, probe_sha, sha):
    data = path.read_text()

    if probe_sha not in data:
        return False

    path.write_text(data.replace(probe_sha, sha))
    return True


def redirected_packages(recipe_data):
    for line in recipe_data.split('\n'):
        line = line.strip()

        if '# check' in line:
            yield from line.split(' ')[2:]


def packages_to_build(repo, packages):
    for package in packages:
        package = package.removesuffix('/unwrap')
        data = (repo / 'pkgs' / package / 'ix.sh').read_text()

        if '# check' in data:
            yield from redirected_packages(data)
        else:
            yield package


def extract_reported_sha(output, probe_sha):
    clean = ANSI_RE.sub(b'', output)
    probe = re.escape(probe_sha.encode())
    patterns = (
        # Current Molot verifies IX graph predict entries after the command.
        re.compile(
            rb'predict mismatch:.*?expected=' + probe +
            rb'\s+actual=([0-9a-f]{64})'
        ),
        # IX's direct fetcher checksum error.
        re.compile(
            rb'got\s+([0-9a-f]{64})\s+checksum,\s+not\s+' + probe
        ),
        # aux/{go,cargo,git} uses the supplied checksum in the .pzd name.
        # Binding the filename to this attempt's probe avoids selecting an
        # adjacent source checksum or another vendoring node's archive.
        re.compile(
            rb'(?m)^([0-9a-f]{64})\s{2,}\S*' + probe + rb'\.pzd\s*$'
        ),
    )
    matches = [
        match.group(1).decode()
        for pattern in patterns
        for match in pattern.finditer(clean)
        if match.group(1).decode() != probe_sha
    ]
    unique = set(matches)

    if not unique:
        raise CandidateFailure('build output contains no checksum for this probe')

    if len(unique) != 1:
        raise CandidateFailure('build output contains conflicting checksums for this probe')

    return unique.pop()


def mc_env(base_env):
    scheme, host = base_env['S3_ENDPOINT'].split('://', 1)
    key = base_env['AWS_ACCESS_KEY_ID']
    secret = base_env['AWS_SECRET_ACCESS_KEY']
    env = dict(base_env)
    env[f'MC_HOST_{MC_ALIAS}'] = f'{scheme}://{key}:{secret}@{host}'
    return env


def cache_uri():
    return f'{MC_ALIAS}/{CACHE_S3_BUCKET}/{CACHE_S3_KEY}'


def cache_read(env):
    res = subprocess.run(
        ('minio-client', 'cat', cache_uri()),
        env=mc_env(env),
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


def cache_update(local_path, env):
    local_lines = Path(local_path).read_text().splitlines()
    remote_lines = cache_read(env).decode().splitlines()
    merged = sorted({line.strip() for line in local_lines + remote_lines if line.strip()})

    fd, tmp = tempfile.mkstemp(prefix='updater-cache.', dir=os.getcwd(), text=True)

    try:
        with os.fdopen(fd, 'w') as out:
            for line in merged:
                out.write(line + '\n')

        subprocess.run(
            ('minio-client', 'cp', tmp, cache_uri()),
            env=mc_env(env),
            check=True,
        )
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    log(f'cache update: local={len(local_lines)} + remote={len(remote_lines)} -> {len(merged)}')


class MolotBuilder:
    def __init__(self, repo, cache_path, base_env):
        self.repo = Path(repo)
        self.env = dict(base_env)
        self.env['IX_EXEC_KIND'] = 'molot'
        self.env['AWS_ACCESS_KEY_ID'] = base_env['AWS_ACCESS_KEY_ID_MOLOT']
        self.env['AWS_SECRET_ACCESS_KEY'] = base_env['AWS_SECRET_ACCESS_KEY_MOLOT']
        self.env['S3_BUCKET'] = 'molot'
        self.env['MOLOT_CACHE'] = str(Path(cache_path).resolve())

    def build(self, packages):
        cmd = ('./ix', 'build', *BUILD_FLAGS, *packages)
        log('run', *cmd, '(molot)')

        res = subprocess.run(
            cmd,
            cwd=self.repo,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            check=False,
        )

        sys.stderr.buffer.write(res.stdout)
        sys.stderr.flush()
        return BuildResult(res.returncode, res.stdout)


class PackageUpdater:
    def __init__(self, repo, builder, branch=IX_BRANCH, env=None):
        self.repo = Path(repo)
        self.builder = builder
        self.branch = branch
        self.env = dict(os.environ if env is None else env)

    def git(self, *args, check=True, capture=False, env=None):
        log('git', *args)
        return subprocess.run(
            ('git', *args),
            cwd=self.repo,
            env=self.env if env is None else env,
            check=check,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            text=capture,
        )

    def dependency_files(self, packages):
        files = set()

        for package in packages:
            res = subprocess.run(
                ('./ix', 'dep', package),
                cwd=self.repo,
                env=self.env,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            )

            files.update(line.strip() for line in res.stdout.splitlines() if line.strip())

        return sorted(files)

    def restore(self):
        self.git('restore', '--source=HEAD', '--staged', '--worktree', '--', '.')

    def show_diff(self):
        self.git('diff')

    def commit_and_push(self, candidate):
        self.git('add', '-A')
        clean = self.git('diff', '--cached', '--quiet', check=False)

        if clean.returncode == 0:
            raise CandidateFailure('recipe rewrite produced no staged change')

        if clean.returncode != 1:
            raise InfrastructureFailure(f'git diff --cached failed with {clean.returncode}')

        self.git('commit', '-m', f'up {candidate.line}')

        push_env = dict(self.env)
        push_env['GIT_ASKPASS'] = 'passenv'
        push_env['GIT_TERMINAL_PROMPT'] = '0'

        # The autonomous fixer publishes independently.  Rebase immediately
        # before push, and retry once if it won the small fetch/push race.
        for attempt in range(2):
            self.git('fetch', 'origin', self.branch)
            self.git('rebase', f'origin/{self.branch}')
            pushed = self.git(
                'push', 'origin', f'HEAD:refs/heads/{self.branch}',
                check=False, env=push_env,
            )

            if pushed.returncode == 0:
                return

            log(f'git push raced with another publisher; retry {attempt + 1}/2')

        raise InfrastructureFailure('git push failed after rebase retries')

    def process(self, candidate):
        if not candidate.packages:
            raise CandidateFailure('Repology record contains no stalix source packages')

        try:
            files = self.dependency_files(candidate.packages)
        except subprocess.CalledProcessError as exc:
            raise CandidateFailure(f'ix dep failed: {exc}') from exc

        paths = [path for name in files if (path := self.repo / 'pkgs' / name).is_file()]

        try:
            accepts_update = any(recipe_accepts_update(path, candidate.old) for path in paths)
        except OSError as exc:
            raise CandidateFailure(f'cannot inspect dependency recipes: {exc}') from exc

        if not accepts_update:
            log(f'nothing to do: {candidate.line}')
            return False

        try:
            build_packages = list(packages_to_build(self.repo, candidate.packages))
        except (OSError, CandidateFailure) as exc:
            raise CandidateFailure(f'cannot resolve build targets: {exc}') from exc
        preflight = self.builder.build(build_packages)

        if preflight.returncode != 0:
            # IX upver treated every unsuccessful preflight as a package
            # miss and continued.  Keep that behavior: transient Molot
            # trouble only postpones this candidate until the next cron run.
            raise CandidateFailure(f'current package does not build (exit {preflight.returncode})')

        # IX derives predicted node UIDs from the expected checksum.  A shared
        # all-zero placeholder therefore gives every Go, Cargo, and git probe
        # the same Molot/Gorn GUID; Gorn then reuses the first task's payload.
        # A fresh invalid checksum keeps each probe isolated while preserving
        # the old updater's checksum-mismatch discovery mechanism.
        probe_sha = secrets.token_hex(32)

        try:
            fixed = sum(
                prepare_recipe(path, candidate.old, candidate.new, probe_sha)
                for path in paths
            )
        except OSError as exc:
            raise CandidateFailure(f'cannot rewrite dependency recipes: {exc}') from exc

        if fixed != 1:
            raise CandidateFailure(f'expected one changed recipe, got {fixed}')

        self.show_diff()
        checksum_build = self.builder.build(build_packages)

        sha = extract_reported_sha(checksum_build.output, probe_sha)

        try:
            changed = sum(install_sha(path, probe_sha, sha) for path in paths)
        except OSError as exc:
            raise CandidateFailure(f'cannot install checksum: {exc}') from exc

        if changed != 1:
            raise CandidateFailure(f'expected one zero-sha recipe, got {changed}')

        log(f'new sha {sha}')
        self.show_diff()
        self.commit_and_push(candidate)
        return True


def clone_ix(dst, env):
    git_url = env.get('IX_UPDATER_GIT_URL', IX_GIT_URL)
    branch = env.get('IX_UPDATER_BRANCH', IX_BRANCH)
    log(f'clone {git_url} branch={branch}')

    subprocess.run(
        ('git', 'clone', '--single-branch', '--branch', branch, git_url, str(dst)),
        env=env,
        check=True,
    )
    subprocess.run(('git', 'config', 'user.name', 'ix updater'), cwd=dst, check=True)
    subprocess.run(
        ('git', 'config', 'user.email', 'ix-updater@users.noreply.github.com'),
        cwd=dst,
        check=True,
    )

    return branch


def require_run_env(env):
    required = (
        'GORN_API',
        'S3_ENDPOINT',
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_ACCESS_KEY_ID_MOLOT',
        'AWS_SECRET_ACCESS_KEY_MOLOT',
        'ETCDCTL_ENDPOINTS',
        'GIT_USER',
        'GIT_PASS',
    )
    missing = [name for name in required if not env.get(name)]

    if missing:
        raise InfrastructureFailure('missing required environment: ' + ', '.join(missing))


def merge_cache(cache_path, env):
    log(f'merge Molot cache {cache_path}')
    subprocess.run(
        ('etcd_lock', CACHE_LOCK_KEY, '--', 'updater', 'cache-update', str(cache_path)),
        env=env,
        check=True,
    )


def run_updater(env):
    require_run_env(env)
    repology_url = env.get('IX_UPDATER_REPOLOGY_URL', REPOLOGY_URL)
    data = fetch_repology(repology_url)
    candidates = list(candidates_from_repology(data))
    log(f'Repology candidates after filters: {len(candidates)}')

    with tempfile.TemporaryDirectory(prefix='updater.', dir=os.getcwd()) as work:
        work = Path(work).resolve()
        repo = work / 'ix'
        cache_path = work / 'molot-cache'
        cache_path.write_bytes(cache_read(env))
        log(f'seeded Molot cache: {cache_path.stat().st_size} bytes')

        branch = clone_ix(repo, env)
        builder = MolotBuilder(repo, cache_path, env)
        updater = PackageUpdater(repo, builder, branch=branch, env=env)
        updated = 0
        failed = 0

        try:
            for candidate in candidates:
                log(f'candidate {candidate.line}')

                try:
                    if updater.process(candidate):
                        updated += 1
                except CandidateFailure as exc:
                    failed += 1
                    log(f'FAILED {candidate.line}: {exc}')
                finally:
                    updater.restore()
        finally:
            merge_cache(cache_path, env)

        log(f'updater done: candidates={len(candidates)} updated={updated} failed={failed}')


def usage():
    print('usage: updater {run | cache-update <local-cache>}', file=sys.stderr)
    raise SystemExit(2)


def main():
    if len(sys.argv) < 2:
        usage()

    command = sys.argv[1]

    if command == 'run' and len(sys.argv) == 2:
        run_updater(os.environ.copy())
        return

    if command == 'cache-update' and len(sys.argv) == 3:
        cache_update(sys.argv[2], os.environ.copy())
        return

    usage()


if __name__ == '__main__':
    main()
