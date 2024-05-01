#!/usr/bin/env python3

import sys
import hashlib
import subprocess

def minio(*args):
    return subprocess.check_output(['minio-client'] + list(args))

def check_exists(p):
    return len(minio('ls', p)) > 5

path = sys.argv[1]
sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()
s3path = f'minio/cas/{sha}'

print(f'will store {path} into {s3path}', file=sys.stderr)

if check_exists(s3path):
    print(f'already have {s3path}', file=sys.stderr)
else:
    minio('put', path, s3path)

print(f'done', file=sys.stderr)
