#!/usr/bin/env python3

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

  2. Sequentially wget each URL, sha256sum it, upload to CAS
     via /bin/cas. Per-URL failures log and move on so a flaky
     upstream for one URL doesn't poison the rest.

  3. For each successful URL: emit `kind=new_sha {sha:<content-sha>}`
     so hf/ghcr subscribers can incrementally update their remotes.

No persistent state — each event handles its own diff window.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys


URLS_PATH = 'pkgs/die/scripts/urls.txt'
MIRROR_GIT = 'http://127.0.0.1:8035/mirror_ix.git'
DEPTH = 3
EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'


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


def fetch_one(url):
    url_sha = hashlib.sha256(url.encode()).hexdigest()
    work = url_sha

    if os.path.exists(work):
        shutil.rmtree(work)

    os.makedirs(work)
    data = os.path.join(work, 'data')

    subprocess.run(['wget', '-O', data, url], check=True)

    res = subprocess.run(
        ['sha256sum', data],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    content_sha = res.stdout.split()[0]

    subprocess.run(['cas', data], check=True)
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
    if len(sys.argv) != 2:
        raise SystemExit('usage: cache_ix_sources <ix-sha>')

    sha = sys.argv[1]
    urls = added_urls(sha)
    log(f'diff window {sha}~{DEPTH}..{sha}: {len(urls)} added URLs')

    new_content_shas = set()

    for url in urls:
        try:
            cs = fetch_one(url)
        except subprocess.CalledProcessError as e:
            log(f'WARN: fetch failed for {url}: {e}')
            continue

        new_content_shas.add(cs)

    log(f'fetched this run: {len(new_content_shas)} unique content shas')

    for content_sha in sorted(new_content_shas):
        emit_new_sha(content_sha)


if __name__ == '__main__':
    main()
