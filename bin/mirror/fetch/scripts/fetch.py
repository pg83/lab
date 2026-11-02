"""
cache_ix_sources — event-driven fetcher of upstream ix sources.
Triggered by /etc/event/git/cache_ix.json on every kind=git
event with payload.repo == 'ix'; argv is the ix HEAD sha at the
time of the event.

Per run:

  1. Acquire the shared etcd lock, read the last processed commit
     from persistent etcd, and bare-clone the local mirror_ix.git.
     Diff urls.txt against that commit, regardless of merge topology.

  2. Sequentially curl each URL, alternating direct and local
     SOCKS5 routes with increasing randomized timeouts, sha256sum it,
     upload to CAS
     via /bin/cas. Failed downloads leave the cursor unchanged; CAS writes
     retry the downloaded file instead of losing it.

  3. Immediately after each successful URL: emit `kind=new_sha {sha:<content-sha>}`
     so mirror subscribers can incrementally update their remotes.

  4. Advance the cursor only after all downloads and events succeed.
     An older event never moves the cursor backwards. --urls is an
     independent manual replay and does not touch the cursor.
"""

import hashlib
import ipaddress
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.parse


URLS_PATH = 'pkgs/die/scripts/urls.txt'
MIRROR_GIT = 'http://127.0.0.1:8035/mirror_ix.git'
CURSOR_KEY = '/mirror/ix/last_processed_commit'
LOCK_NAME = '/lock/mirror/ix/work'


random.seed(int(time.time() * 1000000000000))


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def commit_sha(value):
    if not re.fullmatch('[0-9a-f]{40}', value):
        raise ValueError(f'invalid ix commit: {value!r}')
    return value


def persist_env():
    endpoints = os.environ['ETCD_PERSIST_ENDPOINTS'].strip()
    if not endpoints:
        raise ValueError('ETCD_PERSIST_ENDPOINTS is empty')
    return dict(os.environ, ETCDCTL_ENDPOINTS=endpoints)


def read_cursor():
    value = subprocess.check_output(
        ['etcdctl', 'get', '--print-value-only', CURSOR_KEY],
        env=persist_env(), text=True,
    ).strip()
    if not value:
        raise RuntimeError(f'{CURSOR_KEY} is missing; seed it with the last successful commit')
    return commit_sha(value)


def save_cursor(base, sha):
    # Fence the write with both the cursor and our unique lease-backed lock key.
    # A worker whose lease expired must not overwrite a newer worker's cursor.
    lock_key = os.environ['ETCD_LOCK_KEY']
    if not lock_key.startswith(LOCK_NAME + '/'):
        raise RuntimeError('mirror lock is not held')
    txn = (
        f'value({json.dumps(CURSOR_KEY)}) = {json.dumps(base)}\n'
        f'version({json.dumps(lock_key)}) > "0"\n\n'
        f'put {CURSOR_KEY} {sha}\n\n\n'
    )
    result = subprocess.check_output(
        ['etcdctl', '--write-out=json', 'txn'],
        input=txn, env=persist_env(), text=True,
    )
    if not json.loads(result).get('succeeded'):
        raise RuntimeError('cursor changed or mirror lock expired; cursor was not updated')
    log(f'cursor: {base} -> {sha}')


def clone_repo(sha):
    log(f'cloning {MIRROR_GIT} (--filter=blob:none) for diff at {sha}')

    subprocess.run(
        ['git', 'clone', '--bare', '--filter=blob:none', MIRROR_GIT, 'ix.git'],
        check=True,
    )


def is_ancestor(base, sha):
    result = subprocess.run(['git', '-C', 'ix.git', 'merge-base', '--is-ancestor', base, sha])
    if result.returncode not in (0, 1):
        result.check_returncode()
    return result.returncode == 0


def added_urls(base, sha):
    diff = subprocess.check_output(
        ['git', '-C', 'ix.git', 'diff', '--unified=0', base, sha, '--', URLS_PATH],
    ).decode()

    out = []

    for ln in diff.splitlines():
        if ln.startswith('+') and not ln.startswith('+++'):
            u = ln[1:].strip()

            if u:
                out.append(u)

    return list(dict.fromkeys(out))


# Hosts only our own networks resolve. Everything this worker fetches lands
# in the CAS that subscribers push to the public pkgsrc mirrors, so a recipe that
# fetches from the lab's private s3 (s3.lab.mesh) must never be mirrored.
PRIVATE_SUFFIXES = ('.mesh', '.local', '.gofra', '.localdomain')


def private_url(url):
    host = (urllib.parse.urlsplit(url).hostname or '').lower()

    if not host or host == 'localhost' or host.endswith(PRIVATE_SUFFIXES):
        return True

    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return False


def iter_tout():
    tout = 60

    while True:
        yield 1.5 * tout * (0.5 + random.random())
        tout = min(tout * 1.5, 10000)


def iter_routes():
    while True:
        yield []

        for proxy in P.strip().split(';'):
            if proxy := proxy.strip():
                yield ['--socks5', proxy]


def safe_decode(data):
    try:
        return data.decode()
    except Exception:
        return str(data)


def fetch_url(url, data):
    for route, tout in zip(iter_routes(), iter_tout()):
        cmd = [
            '/bin/timeout', f'{int(tout)}s',
            '/bin/curl',
            '-f',
            '--connect-timeout', str(int(0.1 * tout)),
            '--remove-on-error',
            '--retry', '0',
            '-k',
            '-L',
            '--output', data,
        ] + route + [url]

        log('run', cmd)

        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            message = '\n'.join([str(e), safe_decode(e.output)])

            if 'error: 404' in message:
                raise

            log(f'while fetch {url}: {message}')
            continue

        sys.stderr.buffer.write(output)
        sys.stderr.buffer.flush()
        return


def fetch_one(url):
    url_sha = hashlib.sha256(url.encode()).hexdigest()
    work = url_sha

    if os.path.exists(work):
        shutil.rmtree(work)

    os.makedirs(work)
    data = os.path.join(work, 'data')

    fetch_url(url, data)

    res = subprocess.run(
        ['sha256sum', data],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    content_sha = res.stdout.split()[0]

    while True:
        try:
            subprocess.run(['cas', data], check=True)
            break
        except subprocess.CalledProcessError:
            log(f'CAS upload failed for {url}; keeping downloaded file, retry in 30s')
            time.sleep(30)
    shutil.rmtree(work)

    return content_sha


def emit_new_sha(content_sha):
    log(f'event schedule new_sha {content_sha}')

    subprocess.run(
        ['event', 'schedule', 'new_sha'],
        input=json.dumps({'sha': content_sha}),
        text=True,
        check=True,
    )


def fetch_urls(urls, *, replay=False):
    new_content_shas = set()

    for url in urls:
        if private_url(url):
            log(f'skip private {url}: never mirrored')
            continue

        try:
            cs = fetch_one(url)
        except subprocess.CalledProcessError as e:
            log(f'WARN: fetch failed for {url}: {e}')
            if replay:
                continue
            raise

        if cs not in new_content_shas:
            emit_new_sha(cs)
            new_content_shas.add(cs)

    log(f'fetched this run: {len(new_content_shas)} unique content shas')


def process_commit(sha):
    base = read_cursor()
    if base == sha:
        log(f'already processed {sha}')
        return
    clone_repo(sha)
    if is_ancestor(sha, base):
        log(f'skip old event {sha}; cursor is {base}')
        return
    if not is_ancestor(base, sha):
        raise RuntimeError(f'ix history diverged: cursor {base}, event {sha}')
    urls = added_urls(base, sha)
    log(f'diff {base}..{sha}: {len(urls)} added URLs')
    fetch_urls(urls)
    save_cursor(base, sha)


def main():
    args = sys.argv[1:]
    if args == ['--urls']:
        urls = list(dict.fromkeys(line.strip() for line in sys.stdin if line.strip()))
        log(f'replay: {len(urls)} URLs')
        fetch_urls(urls, replay=True)
    elif len(args) == 2 and args[0] == '--locked':
        process_commit(commit_sha(args[1]))
    elif len(args) == 1:
        sha = commit_sha(args[0])
        os.execvpe('etcd_lock', [
            'etcd_lock', LOCK_NAME, '--',
            sys.executable, os.path.abspath(__file__), '--locked', sha,
        ], persist_env())
    else:
        raise SystemExit('usage: cache_ix_sources <ix-sha> | --urls < urls.txt')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Gorn retries exit 1; avoid a tight retry loop on an unavailable source.
        import traceback
        traceback.print_exc()
        time.sleep(30)
        sys.exit(1)
