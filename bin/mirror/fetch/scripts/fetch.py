#!/usr/bin/env python3

import sys
import time
import hashlib
import subprocess

import urllib.request as ur


time.sleep(100)


PART = '''
{sha}.touch:
	rm -rf {sha}
	/bin/fetcher {url} {sha}/data __skip__
	cas {sha}/data
	rm -rf {sha}
	touch {sha}.touch

all: {sha}.touch

'''


def make_part(u):
    sha = hashlib.sha256(u.encode()).hexdigest()
    return PART.replace('{sha}', sha).replace('{url}', u)


def it_parts():
    yield '.ONESHELL:'

    for u in ur.urlopen('https://raw.githubusercontent.com/pg83/ix/main/pkgs/die/scripts/urls.txt').read().decode().split('\n'):
        yield make_part(u)

cmd = ''.join(it_parts())

subprocess.run(['timeout', '1h', 'make', '-k', '-j', '10', '-f', '/proc/self/fd/0', 'all'], input=cmd.encode(), check=True)
