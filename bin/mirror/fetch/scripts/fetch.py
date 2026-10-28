"""
cache_ix_sources — event-driven fetcher of upstream ix sources.
Triggered by /etc/event/git/cache_ix.json on every kind=git
event with payload.repo == 'ix'; argv is the ix HEAD sha at the
time of the event.

Per run:

  1. Bare-clone (--filter=blob:none) the local mirror_ix.git;
     `git diff <sha>~DEPTH..<sha> -- pkgs/die/scripts/urls.txt`
     yields the added URL lines (the '+' rows). DEPTH=3 keeps
     a 2-event buffer for missed/failed prior events; CAS-dedup
     absorbs whatever is re-fetched.

  2. Sequentially curl each URL, alternating direct and local
     SOCKS5 routes with increasing randomized timeouts, sha256sum it,
     upload to CAS
     via /bin/cas. A missing upstream URL is skipped; failed CAS writes
     retry the downloaded file instead of losing it.

  3. Immediately after each successful URL: emit `kind=new_sha {sha:<content-sha>}`
     so hf/ghcr subscribers can incrementally update their remotes.

No persistent state — each event handles its own diff window.
"""

import hashlib
import ipaddress
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.parse


URLS_PATH = 'pkgs/die/scripts/urls.txt'
MIRROR_GIT = 'http://127.0.0.1:8035/mirror_ix.git'
DEPTH = 3
EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'


random.seed(int(time.time() * 1000000000000))


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def added_urls(sha):
    log(f'cloning {MIRROR_GIT} (--filter=blob:none) for diff at {sha}')

    subprocess.run(
        ['git', 'clone', '--bare', '--filter=blob:none', MIRROR_GIT, 'ix.git'],
        check=True,
    )

    res = subprocess.run(
        ['git', '-C', 'ix.git', 'rev-parse', f'{sha}~{DEPTH}'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    if res.returncode == 0:
        base = res.stdout.strip()
    else:
        log(f'history shorter than {DEPTH}, falling back to empty tree')
        base = EMPTY_TREE

    diff = subprocess.check_output(
        ['git', '-C', 'ix.git', 'diff', '--unified=0', base, sha, '--', URLS_PATH],
    ).decode()

    out = []

    for ln in diff.splitlines():
        if ln.startswith('+') and not ln.startswith('+++'):
            u = ln[1:].strip()

            if u:
                out.append(u)

    return out


# Hosts only our own networks resolve. Everything this worker fetches lands
# in the CAS that hf/ghcr push to the public pkgsrc mirrors, so a recipe that
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


def main():
    if sys.argv[1:] == ['--urls']:
        urls = list(dict.fromkeys(line.strip() for line in sys.stdin if line.strip()))
        log(f'replay: {len(urls)} URLs')
    elif len(sys.argv) == 2:
        sha = sys.argv[1]
        urls = added_urls(sha)
        log(f'diff window {sha}~{DEPTH}..{sha}: {len(urls)} added URLs')
    else:
        raise SystemExit('usage: cache_ix_sources <ix-sha> | --urls < urls.txt')

    new_content_shas = set()

    for url in urls:
        if private_url(url):
            log(f'skip private {url}: never mirrored')
            continue

        try:
            cs = fetch_one(url)
        except subprocess.CalledProcessError as e:
            log(f'WARN: fetch failed for {url}: {e}')
            continue

        if cs not in new_content_shas:
            emit_new_sha(cs)
            new_content_shas.add(cs)

    log(f'fetched this run: {len(new_content_shas)} unique content shas')

if __name__ == '__main__':
    main()
