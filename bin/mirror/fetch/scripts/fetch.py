#!/usr/bin/env python3

import os
import sys
import hashlib
import subprocess

import urllib.request as ur

PART = '''
{sha}.touch:
	rm -rf {sha}
	wget -O {sha} --no-check-certificate {url}
	cas {sha}
	rm {sha}
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


where = sys.argv[1]

try:
    os.makedirs(where)
except OSError:
    pass

os.environ['HOME'] = where

cmd = ''.join(it_parts())

subprocess.run(['timeout', '1h', 'make', '-k', '-j', '10', '-C', where, '-f', '/proc/self/fd/0', 'all'], input=cmd.encode(), check=True)
