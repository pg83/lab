#!/usr/bin/env python3

"""Promote one fully built pg83/ix revision to stal-ix/ix.

The daily scheduler enqueues this worker under its own etcd work lock.
Pin the development SHA, merge it onto stable locally, and build the entire
CI tier through Molot. Only a successful build can publish a `stable` PR
and its two-parent merge commit. A moving development branch is harmless;
a moving stable branch requires building a new merge before publishing.

The PR uses an immutable snapshot branch so it contains exactly the source
revision that was built. GitHub's merge API uses the token owner's identity;
publish our local merge instead to attribute it to scp-2603[bot]. Pushing the
merge into the PR's base branch also marks the PR merged on GitHub.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


MIRROR_URL = 'http://127.0.0.1:8035/mirror_ix.git'
SOURCE_REPO = 'pg83/ix'
TARGET_REPO = 'stal-ix/ix'
BRANCH = 'main'
BUILD_COMMAND = ('./ix', 'build', 'set/ci/tier/0', '--seed=1')
TOKEN_URL = 'http://127.0.0.1:8022/github/token'
BOT_NAME = 'SCP-2603'
BOT_EMAIL = '351190792+scp-2603[bot]@users.noreply.github.com'
PUSH_ATTEMPTS = 10
RETRY_DELAY_S = 15


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def read_env(env):
    out = dict(env)
    for name in (
        'GIT_PASS', 'GIT_ASKPASS', 'SSH_ASKPASS', 'SSH_AUTH_SOCK',
        'GH_TOKEN', 'GITHUB_TOKEN',
    ):
        out.pop(name, None)
    out['GIT_TERMINAL_PROMPT'] = '0'
    for role in ('AUTHOR', 'COMMITTER'):
        out[f'GIT_{role}_NAME'] = BOT_NAME
        out[f'GIT_{role}_EMAIL'] = BOT_EMAIL
        out.pop(f'GIT_{role}_DATE', None)
    return out


def load_token(env):
    url = env.get('IX_MERGER_TOKEN_URL', TOKEN_URL)
    with urllib.request.urlopen(url, timeout=10) as response:
        token = response.read().decode().strip()
    if not token:
        raise RuntimeError('empty GitHub token')
    return token


class GitHub:
    def __init__(self, token):
        self.token = token

    def request(self, method, path, body=None):
        request = urllib.request.Request(
            'https://api.github.com' + path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={
                'Authorization': f'Bearer {self.token}',
                'Accept': 'application/vnd.github+json',
                'Content-Type': 'application/json',
                'User-Agent': 'ix-updater-merger',
                'X-GitHub-Api-Version': '2022-11-28',
            },
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    def stable_pr(self, branch, source, base, tree):
        query = urllib.parse.urlencode({
            'state': 'all', 'head': f'pg83:{branch}', 'base': BRANCH,
        })
        path = f'/repos/{TARGET_REPO}/pulls'
        body = (
            f'Promote `{SOURCE_REPO}@{source}` to `{TARGET_REPO}:{BRANCH}`.\n\n'
            f'Full Molot build passed: `{" ".join(BUILD_COMMAND)}`.\n\n'
            f'Base: `{base}`\n\nBuilt tree: `{tree}`\n\n'
            'The source branch is pinned. Publication keeps a two-parent '
            'merge commit authored by `scp-2603[bot]`.'
        )
        matches = self.request('GET', path + '?' + query)
        if matches:
            pr = matches[0]
            if pr['state'] != 'open':
                raise RuntimeError(f"snapshot PR #{pr['number']} is closed")
            if pr['body'] != body:
                pr = self.request('PATCH', path + f"/{pr['number']}", {'body': body})
        else:
            pr = self.request('POST', path, {
                'title': 'stable', 'head': f'pg83:{branch}', 'base': BRANCH,
                'body': body, 'maintainer_can_modify': False,
            })
        if pr['head']['sha'] != source or pr['base']['ref'] != BRANCH:
            raise RuntimeError('PR no longer points at the built source revision')
        return pr


class Merger:
    def __init__(self, repo, env):
        self.repo = Path(repo)
        self.env = read_env(env)
        self.mirror = env.get('IX_MERGER_MIRROR_URL', MIRROR_URL)
        self.source_url = env.get('IX_MERGER_SOURCE_URL', f'https://github.com/{SOURCE_REPO}.git')
        self.target_url = env.get('IX_MERGER_TARGET_URL', f'https://github.com/{TARGET_REPO}.git')
        self.token = None
        self.github = None

    def git(self, *args, capture=False, check=True, publish=False):
        env = dict(self.env)
        if publish:
            if self.token is None:
                self.token = load_token(self.env)
                self.github = GitHub(self.token)
            env['GIT_USER'] = env.get('GIT_USER', 'pg83')
            env['GIT_PASS'] = self.token
            env['GIT_ASKPASS'] = 'passenv'
        log('git', *args)
        return subprocess.run(
            ('git', *args), cwd=self.repo, env=env, check=check,
            stdout=subprocess.PIPE if capture else None, text=True,
        )

    def output(self, *args):
        return self.git(*args, capture=True).stdout.strip()

    def fetch(self, url):
        self.git('fetch', '--no-tags', url, f'refs/heads/{BRANCH}')
        return self.output('rev-parse', 'FETCH_HEAD')

    def ancestor(self, ancestor, revision):
        result = self.git('merge-base', '--is-ancestor', ancestor, revision, check=False)
        if result.returncode not in (0, 1):
            result.check_returncode()
        return result.returncode == 0

    def checkout(self):
        subprocess.run(
            ('git', 'clone', '--single-branch', '--branch', BRANCH,
             self.mirror, str(self.repo)), env=self.env, check=True,
        )
        self.git('config', 'commit.gpgsign', 'false')
        # The local mirror warms the clone; pin the authoritative GitHub ref.
        return self.fetch(self.source_url)

    def prepare(self, source, base):
        self.git('checkout', '--detach', base)
        self.git('merge', '--no-ff', '--no-edit', '-m', 'stable', source)
        parents = self.output('rev-list', '--parents', '-n', '1', 'HEAD').split()[1:]
        if parents != [base, source]:
            raise RuntimeError('stable promotion must have exactly base and source as parents')
        return self.output('rev-parse', 'HEAD^{tree}')

    def build(self):
        env = dict(self.env)
        env['IX_EXEC_KIND'] = 'molot'
        env['S3_BUCKET'] = 'molot'
        log('run', *BUILD_COMMAND, '(full CI tier, molot)')
        subprocess.run(BUILD_COMMAND, cwd=self.repo, env=env, check=True)
        # No formatting/lint gate: the built inputs must simply stay the
        # same tracked tree that will be published.
        self.git('diff', '--quiet', 'HEAD', '--')

    def snapshot(self, source):
        branch = f'merger/stable-{source}'
        ref = f'refs/heads/{branch}'
        existing = self.output('ls-remote', '--heads', self.source_url, ref)
        if existing and existing.split()[0] != source:
            raise RuntimeError(f'{branch} already points to another revision')
        self.git('push', self.source_url, f'{source}:{ref}', publish=True)
        return branch

    def publish(self, source, base, tree):
        branch = self.snapshot(source)
        pr = self.github.stable_pr(branch, source, base, tree)
        message = (
            f"Merge pull request #{pr['number']} from pg83/{branch}\n\nstable\n\n"
            f'Build: {" ".join(BUILD_COMMAND)}\nBuilt tree: {tree}'
        )
        # Only the message changes after the build, never its tree/parents.
        self.git('commit', '--amend', '-m', message)
        if self.output('rev-parse', 'HEAD^{tree}') != tree:
            raise RuntimeError('merge tree changed after the successful build')
        merge = self.output('rev-parse', 'HEAD')
        log(f"publish {merge}; PR {pr['html_url']}")
        pushed = self.git(
            'push', self.target_url, f'{merge}:refs/heads/{BRANCH}',
            publish=True, check=False,
        )
        if pushed.returncode == 0:
            log(f'stable published: {merge}; source={source}; tree={tree}')
            return True
        # A lost push response may still have published the commit.
        current = self.fetch(self.target_url)
        if self.ancestor(merge, current):
            log(f'stable published despite lost push response: {merge}')
            return True
        return False

    def run(self):
        source = self.checkout()
        log(f'pinned source: {source}')
        built_base = None
        tree = None
        for attempt in range(1, PUSH_ATTEMPTS + 1):
            base = self.fetch(self.target_url)
            if self.ancestor(source, base):
                log(f'stable already contains {source}; nothing to merge')
                return
            if base != built_base:
                tree = self.prepare(source, base)
                self.build()
                built_base = base
            current = self.fetch(self.target_url)
            if current != base:
                log(f'stable moved {base} -> {current}; rebuild the merge')
                continue
            try:
                if self.publish(source, base, tree):
                    return
            except (urllib.error.URLError, subprocess.CalledProcessError) as exc:
                log(f'publication failed: {exc}')
            log(f'publication attempt {attempt}/{PUSH_ATTEMPTS} failed')
            if attempt < PUSH_ATTEMPTS:
                time.sleep(RETRY_DELAY_S)
        raise RuntimeError('stable publication retries exhausted')


def main():
    if sys.argv[1:] != ['run']:
        raise SystemExit('usage: updater_merger run')
    env = os.environ.copy()
    required = ('GORN_API', 'S3_ENDPOINT', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY')
    missing = [name for name in required if not env.get(name)]
    if missing:
        raise RuntimeError('missing environment: ' + ', '.join(missing))
    with tempfile.TemporaryDirectory(prefix='updater-merger.', dir=os.getcwd()) as work:
        Merger(Path(work).resolve() / 'ix', env).run()


if __name__ == '__main__':
    main()
