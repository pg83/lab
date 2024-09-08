#!/usr/bin/env python3

import os
import sys
import json
import subprocess


def get_data():
    cmd = [
        'lsblk',
        '--json',
        '-A',
        '-p',
        '-o', 'NAME,LABEL,PTUUID,UUID,PARTUUID',
    ]

    return subprocess.check_output(cmd).decode()


def get_json():
    return json.loads(get_data())


def flatten(x):
    yield x

    if 'children' in x:
        for c in x['children']:
            yield from flatten(c)


def get_items():
    for x in get_json()['blockdevices']:
        yield from flatten(x)


def uniq_items():
    v = set()

    for i in get_items():
        if i['name'] in v:
            continue

        v.add(i['name'])

        yield i


for i in uniq_items():
    for k, v in i.items():
        if v and k in ('ptuuid', 'uuid', 'partuuid'):
            os.symlink(i['name'], sys.argv[1] + '/' + v)
