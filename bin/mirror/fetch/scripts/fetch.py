#!/usr/bin/env python3

"""
cache_ix_sources — event-driven fetcher of upstream ix sources.
Triggered by /etc/event/git/cache_ix.json on every kind=git
event with payload.repo == 'ix'; argv is the ix HEAD sha at the
time of the event.

Per run:

  1. Bare-clone (--filter=blob:none) the local mirror_ix.git;
     `git show <sha>:pkgs/die/scripts/urls.txt` extracts the
     urls list as it was at <sha>. Reading from the mirror at
     the exact event sha keeps the URL set consistent with the
     event regardless of how stale upstream is.

  2. Pull manifest of already-fetched URL-shas from MinIO
     (mirror/mirror/fetched.txt). Diff with urls.txt → todo.

  3. make -j10 -k on the full delta (no per-tick batch — one
     ix push, one fetch). Each rule downloads via /bin/fetcher,
     uploads to CAS, captures the content sha into a .csha
     sidecar.

  4. For each completed URL: read sidecar to get content sha,
     emit `kind=new_sha {sha:<content-sha>}` so hf/ghcr
     subscribers can incrementally update their remotes.

  5. Union manifest with locally-completed URL-shas, push back.

The manifest file MUST exist in MinIO before the first run:

    echo -n | minio-client pipe minio/mirror/mirror/fetched.txt

Empty body = valid first-run state. Missing file makes mc cat
fail loud — that's a deployment bug, not "first run". Manual
`mc rm` forces a full re-fetch once the empty file is back.
"""

import hashlib
import json
import os
import subprocess
import sys


URLS_PATH = 'pkgs/die/scripts/urls.txt'
MIRROR_GIT = 'http://127.0.0.1:8035/mirror_ix.git'
MANIFEST = 'mirror/mirror/fetched.txt'


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def mc(*args, capture=False):
    log('minio-client', *args)

    return subprocess.run(
        ('minio-client',) + args,
        check=True,
        stdout=subprocess.PIPE if capture else None,
        text=True if capture else None,
    )


def load_manifest():
    body = mc('cat', MANIFEST, capture=True).stdout

    return {ln.strip() for ln in body.splitlines() if ln.strip()}


def save_manifest(shas):
    tmp = 'fetched.txt.tmp'

    with open(tmp, 'w') as f:
        for s in sorted(shas):
            f.write(s + '\n')

    mc('cp', tmp, MANIFEST)


def fetch_urls(sha):
    log(f'cloning {MIRROR_GIT} (--filter=blob:none) for urls.txt at {sha}')

    subprocess.run(
        ['git', 'clone', '--bare', '--filter=blob:none', MIRROR_GIT, 'ix.git'],
        check=True,
    )

    body = subprocess.check_output(
        ['git', '-C', 'ix.git', 'show', f'{sha}:{URLS_PATH}'],
    ).decode()

    return [u.strip() for u in body.split('\n') if u.strip()]


def emit_new_sha(content_sha):
    log(f'event schedule new_sha {content_sha}')

    subprocess.run(
        ['event', 'schedule', 'new_sha'],
        input=json.dumps({'sha': content_sha}),
        text=True,
        check=True,
    )


PART = '''
{url_sha}.touch:
\trm -rf {url_sha}
\t/bin/fetcher {url} {url_sha}/data __skip__
\tcas {url_sha}/data
\tsha256sum {url_sha}/data | awk '{{print $$1}}' > {url_sha}.csha
\trm -rf {url_sha}
\ttouch {url_sha}.touch

all: {url_sha}.touch

'''


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: cache_ix_sources <ix-sha>')

    sha = sys.argv[1]

    done = load_manifest()
    log(f'manifest: {len(done)} URLs already fetched')

    todo = [(u, hashlib.sha256(u.encode()).hexdigest()) for u in fetch_urls(sha)]
    todo = [(u, s) for u, s in todo if s not in done]
    log(f'delta: {len(todo)} new URLs')

    if not todo:
        return

    mk = '.ONESHELL:\n' + ''.join(
        PART.replace('{url_sha}', s).replace('{url}', u) for u, s in todo
    )

    # make -k: keep going past per-target failures, capture whatever
    # did complete. The manifest merge below only records successes,
    # so a flaky upstream for one URL doesn't poison the rest.
    subprocess.run(
        ['timeout', '1h', 'make', '-k', '-j', '10', '-f', '/proc/self/fd/0', 'all'],
        input=mk.encode(),
        check=False,
    )

    new_url_shas = set()
    new_content_shas = set()

    for fn in sorted(os.listdir('.')):
        if not fn.endswith('.touch'):
            continue

        url_sha = fn[:-len('.touch')]
        new_url_shas.add(url_sha)

        csha_path = f'{url_sha}.csha'

        if not os.path.exists(csha_path):
            log(f'WARN: {csha_path} missing for completed url_sha={url_sha}')
            continue

        content_sha = open(csha_path).read().strip()

        if content_sha:
            new_content_shas.add(content_sha)

    log(f'fetched this run: {len(new_url_shas)} URLs, {len(new_content_shas)} unique content shas')

    if not new_url_shas:
        return

    save_manifest(done | new_url_shas)
    log(f'manifest pushed: {len(done | new_url_shas)} URLs total')

    # Emit new_sha events after the manifest write so a crash mid-emit
    # doesn't lose progress — these are idempotent on subscribers anyway.
    for content_sha in sorted(new_content_shas):
        emit_new_sha(content_sha)


if __name__ == '__main__':
    main()
