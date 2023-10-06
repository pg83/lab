import os
import sys
import functools
import subprocess

import urllib.error as ue
import urllib.request as ur

import core.error as ce


def fetch_url_data(url):
    return ur.urlopen(url).read()


def fetch_url_impl(url, out):
    print(f'fetch {url} into {out}')

    def iter_chunks():
        r = ur.urlopen(url)

        while True:
            c = r.read(1 * 1024 * 1024)

            if c:
                yield c
            else:
                return

    with open(out, 'wb') as f:
        cnt = 0

        for c in iter_chunks():
            cnt += len(c)

            print('\r' + chr(27) + '[0K' + f'got {cnt} bytes', end='')

            f.write(c)

        print('')


def fetch_url_wget(wget, url, out):
    return subprocess.check_call([wget, '--no-check-certificate', '-O', out, url], shell=False)


def fetch_url_curl(curl, url, out):
    return subprocess.check_call([curl, '-k', '-L', '--output', out, url], shell=False)


def iter_bin():
    yield 'wget', fetch_url_wget
    yield 'curl', fetch_url_curl


def iter_meth():
    for p in ['/ix/realm/boot/bin', '/usr/bin']:
        for n, m in iter_bin():
            pp = os.path.join(p, n)

            if os.path.isfile(pp):
                yield functools.partial(m, pp)

    yield fetch_url_impl


def fetch_url(url, out):
    print(f'fetch {url} into {out}', file=sys.stderr)

    for meth in iter_meth():
        try:
            return meth(url, out)
        except Exception as e:
            print(e)
