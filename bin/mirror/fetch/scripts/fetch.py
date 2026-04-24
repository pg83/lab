#!/usr/bin/env python3

"""
cache_ix_sources — incremental fetch of upstream ix sources into
the cluster CAS, 100 random URLs per tick. Each cron tick:

  1. Pull manifest of already-fetched URL-shas from MinIO
     (mirror/mirror/fetched.txt, one sha per line, empty if first run).
  2. Walk upstream urls.txt; filter to URLs whose sha is NOT in the
     manifest. Pick BATCH random ones from what's left.
  3. make -j10 on just that batch. Each success → fetcher downloads,
     cas uploads, touch {sha}.touch.
  4. Union existing manifest with locally-completed shas, push back.

Small batches at 100s cadence keep upstream bandwidth smooth and
no single tick needs an hour. Random sampling means the three
hosts' consecutive ticks (via the cluster lock) don't redundantly
work the same URL order — coverage of the full delta is stochastic
but even in expectation.

No local state needed between ticks; manual `mc rm` of the manifest
forces a full re-fetch.
"""

import hashlib
import os
import random
import subprocess
import sys
import urllib.request


BATCH = 100


URLS_TXT = 'https://raw.githubusercontent.com/pg83/ix/main/pkgs/die/scripts/urls.txt'
MANIFEST = 'mirror/mirror/fetched.txt'


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def mc_env():
    scheme, host = os.environ['S3_ENDPOINT'].split('://', 1)
    env = dict(os.environ)
    env['MC_HOST_mirror'] = f"{scheme}://{os.environ['AWS_ACCESS_KEY_ID']}:{os.environ['AWS_SECRET_ACCESS_KEY']}@{host}"

    return env


def mc(*args, env, capture=False, check=True):
    log('minio-client', *args)

    return subprocess.run(
        ('minio-client',) + args,
        env=env,
        check=check,
        stdout=subprocess.PIPE if capture else None,
        text=True if capture else None,
    )


def load_manifest(env):
    res = mc('cat', MANIFEST, env=env, capture=True, check=False)

    if res.returncode != 0:
        log('manifest not found on MinIO — assuming empty (first run)')

        return set()

    return {ln.strip() for ln in res.stdout.splitlines() if ln.strip()}


def save_manifest(shas, env):
    tmp = 'fetched.txt.tmp'

    with open(tmp, 'w') as f:
        for s in sorted(shas):
            f.write(s + '\n')

    mc('cp', tmp, MANIFEST, env=env)


def fetch_urls():
    body = urllib.request.urlopen(URLS_TXT).read().decode()

    return [u.strip() for u in body.split('\n') if u.strip()]


PART = '''
{sha}.touch:
\trm -rf {sha}
\t/bin/fetcher {url} {sha}/data __skip__
\tcas {sha}/data
\trm -rf {sha}
\ttouch {sha}.touch

all: {sha}.touch

'''


def main():
    env = mc_env()

    done = load_manifest(env)
    log(f'manifest: {len(done)} URLs already fetched')

    todo = [(u, hashlib.sha256(u.encode()).hexdigest()) for u in fetch_urls()]
    todo = [(u, s) for u, s in todo if s not in done]
    log(f'delta: {len(todo)} new URLs')

    if not todo:
        return

    random.shuffle(todo)
    batch = todo[:BATCH]
    log(f'this tick: {len(batch)} URLs (random sample)')

    mk = '.ONESHELL:\n' + ''.join(PART.replace('{sha}', s).replace('{url}', u) for u, s in batch)

    # make -k: keep going past per-target failures, capture whatever
    # did complete. The manifest merge below only records successes,
    # so a flaky upstream for one URL doesn't poison the rest.
    subprocess.run(
        ['timeout', '1h', 'make', '-k', '-j', '10', '-f', '/proc/self/fd/0', 'all'],
        input=mk.encode(),
        check=False,
    )

    new = {fn[:-len('.touch')] for fn in os.listdir('.') if fn.endswith('.touch')}
    log(f'fetched this tick: {len(new)}')

    if not new:
        return

    save_manifest(done | new, env)
    log(f'manifest pushed: {len(done | new)} URLs total')


if __name__ == '__main__':
    main()
