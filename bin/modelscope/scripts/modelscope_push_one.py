#!/usr/bin/env python3

"""Publish one CAS archive to the ModelScope dataset."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request


BASE = 'https://www.modelscope.ai'
REPO = 'pg1983/pkgsrc'
TOKEN = os.environ['MODELSCOPE_TOKEN']


def headers():
    return {
        'Authorization': 'Bearer ' + TOKEN,
        'Cookie': 'm_session_id=' + TOKEN,
        'User-Agent': 'ix-modelscope-mirror/1',
        'Content-Type': 'application/json',
    }


def api(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(BASE + path, data=data, headers=headers())
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)
    if result.get('Success') is False or result.get('Code') not in (None, 200, '200'):
        raise RuntimeError('ModelScope: ' + str(result.get('Message', result.get('Code'))))
    return result.get('Data', result)


def published(sha, dest):
    # The download endpoint also answers HEAD 200 for missing files.
    # Consult repository metadata instead, scoped to the SHA prefix.
    page = 1
    while True:
        query = urllib.parse.urlencode({
            'Revision': 'master', 'Root': 'cas/' + sha[:2],
            'Recursive': 'True', 'PageNumber': page, 'PageSize': 200,
        })
        entries = api('/api/v1/datasets/' + REPO + '/repo/tree?' + query)['Files']
        for entry in entries:
            if entry.get('Path') == dest:
                if entry.get('Sha256') != sha:
                    raise RuntimeError('ModelScope path has a different SHA256: ' + dest)
                return True
        if len(entries) < 200:
            return False
        page += 1


def upload(sha, size, path):
    result = api('/api/v1/repos/datasets/' + REPO + '/info/lfs/objects/batch', {
        'operation': 'upload', 'objects': [{'oid': sha, 'size': size}],
    })
    objects = result['objects']
    # Like the official SDK: an omitted object is already stored globally.
    # It still needs a repository reference in the subsequent commit.
    if not objects:
        return 'reused'
    obj = next((obj for obj in objects if obj['oid'] == sha), None)
    if obj is None:
        raise RuntimeError('LFS batch did not return the requested SHA: ' + sha)
    if obj.get('error'):
        raise RuntimeError('LFS: ' + str(obj['error']))
    action = obj.get('actions', {}).get('upload')
    if not action:
        return 'reused'
    url = action['href']
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ''
    if parsed.scheme != 'https' or not (host == 'modelscope.ai' or host.endswith('.modelscope.ai')):
        raise RuntimeError('Unexpected ModelScope upload host: ' + host)
    upload_headers = headers()
    upload_headers.update({'Content-Length': str(size), 'Content-Type': 'application/octet-stream'})
    with path.open('rb') as source:
        request = urllib.request.Request(url, data=source, method='PUT', headers=upload_headers)
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read()
    if body:
        result = json.loads(body)
        if result.get('Success') is False or result.get('Code') not in (None, 200, '200'):
            raise RuntimeError('LFS upload rejected: ' + str(result.get('Message', result.get('Code'))))
    return 'uploaded'


def main():
    sha = sys.argv[1]
    if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('expected a SHA256 digest')
    dest = 'cas/' + sha[:2] + '/' + sha
    if published(sha, dest):
        print(f'modelscope: {sha} already published', flush=True)
        return
    with tempfile.TemporaryDirectory(prefix='modelscope-', dir='.') as scratch:
        path = Path(scratch).resolve() / sha
        subprocess.run(['minio-client', '--quiet', 'get', 'minio/cas/' + sha, str(path)], check=True)
        with path.open('rb') as source:
            actual = hashlib.file_digest(source, 'sha256').hexdigest()
        if actual != sha:
            raise RuntimeError('CAS archive SHA256 mismatch: ' + sha)
        size = path.stat().st_size
        state = upload(sha, size, path)
        api('/api/v1/repos/datasets/' + REPO + '/commit/master', {
            'commit_message': 'Mirror IX source archive ' + sha,
            'actions': [{
                'action': 'create', 'path': dest, 'type': 'lfs', 'size': size,
                'sha256': sha, 'content': '', 'encoding': '',
            }],
        })
        print(f'modelscope: {sha} published ({state}, {size} bytes)', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        message = (type(error).__name__ + ': ' + str(error)).replace(TOKEN, '<redacted>')
        message = message.replace(os.environ.get('MC_HOST_minio', 'unused-secret-placeholder'), '<redacted>')
        print('modelscope: ' + message, file=sys.stderr, flush=True)
        sys.exit(1)
