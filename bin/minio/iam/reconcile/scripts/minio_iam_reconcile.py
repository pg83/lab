#!/usr/bin/env python3

import json
import os
import secrets
import string
import subprocess
import sys


BUCKETS = (
    'cas',
    'cix',
    'etcd',
    'geesefs',
    'gorn',
    'loki',
    'mirror',
    'ogorod',
    'samogon',
)


def bucket_policy(bucket):
    return {
        'Version': '2012-10-17',
        'Statement': [
            {
                'Sid': 'ReadAll',
                'Effect': 'Allow',
                'Action': [
                    's3:GetObject',
                    's3:GetBucketLocation',
                    's3:ListBucket',
                    's3:ListBucketMultipartUploads',
                    's3:ListMultipartUploadParts',
                ],
                'Resource': [
                    'arn:aws:s3:::*',
                ],
            },
            {
                'Sid': 'WriteOwn',
                'Effect': 'Allow',
                'Action': [
                    's3:PutObject',
                    's3:DeleteObject',
                    's3:AbortMultipartUpload',
                ],
                'Resource': [
                    f'arn:aws:s3:::{bucket}',
                    f'arn:aws:s3:::{bucket}/*',
                ],
            },
        ],
    }


SPEC = {
    'policies': {f'{b}-rw': bucket_policy(b) for b in BUCKETS},
    'users': {b: {'policy': f'{b}-rw'} for b in BUCKETS},
}


CREDS_REQUIRED = (
    'AWS_ACCESS_KEY_ID',
    'AWS_SECRET_ACCESS_KEY',
    'S3_ENDPOINT',
    'ETCDCTL_ENDPOINTS',
)


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def mc_env():
    scheme, host = os.environ['S3_ENDPOINT'].split('://', 1)
    env = dict(os.environ)
    env['MC_HOST_minio'] = f"{scheme}://{os.environ['AWS_ACCESS_KEY_ID']}:{os.environ['AWS_SECRET_ACCESS_KEY']}@{host}"

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


def etcd_get(path):
    res = subprocess.run(
        ['etcdctl', 'get', '--print-value-only', path],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )

    return res.stdout.rstrip('\n')


def etcd_put(path, value):
    subprocess.run(['etcdctl', 'put', path], input=value, check=True, text=True)


def gen_key(n):
    alpha = string.ascii_letters + string.digits

    return ''.join(secrets.choice(alpha) for _ in range(n))


def ensure_etcd_creds(user):
    base = f'/s3/iam/{user}'

    key = etcd_get(base + '/key')

    if not key:
        key = gen_key(20)
        etcd_put(base + '/key', key)
        log(f'etcd: generated key for {user}')

    sec = etcd_get(base + '/secret')

    if not sec:
        sec = gen_key(40)
        etcd_put(base + '/secret', sec)
        log(f'etcd: generated secret for {user}')

    return key, sec


def reconcile_policies(env):
    for name, doc in SPEC['policies'].items():
        path = f'./policy.{name}.json'

        with open(path, 'w') as f:
            json.dump(doc, f, indent=2)

        mc('admin', 'policy', 'create', 'minio', name, path, env=env)


def user_exists(env, key):
    res = mc('admin', 'user', 'info', 'minio', key, env=env, capture=True, check=False)

    return res.returncode == 0


def attached_policies(env, key):
    res = mc('admin', 'policy', 'entities', 'minio', '--user', key, '--json', env=env, capture=True)
    data = json.loads(res.stdout)
    out = set()

    result = data.get('result', data)

    for m in result.get('userMappings', []):
        if m.get('user') == key:
            for p in m.get('policies', []):
                out.add(p)

    for m in result.get('policyMappings', []):
        if key in m.get('users', []):
            out.add(m.get('policy'))

    return out


def reconcile_user(env, name, cfg):
    key, sec = ensure_etcd_creds(name)

    if not user_exists(env, key):
        mc('admin', 'user', 'add', 'minio', key, sec, env=env)
        log(f'minio: created user {name} (access_key={key})')

    desired = {cfg['policy']}
    actual = attached_policies(env, key)

    for p in actual - desired:
        mc('admin', 'policy', 'detach', 'minio', p, '--user', key, env=env)
        log(f'minio: detached {p} from {name}')

    for p in desired - actual:
        mc('admin', 'policy', 'attach', 'minio', p, '--user', key, env=env)
        log(f'minio: attached {p} to {name}')


def main():
    for k in CREDS_REQUIRED:
        if not os.environ.get(k):
            raise SystemExit(f'{k} not set')

    env = mc_env()

    reconcile_policies(env)

    for name, cfg in SPEC['users'].items():
        reconcile_user(env, name, cfg)


if __name__ == '__main__':
    main()
