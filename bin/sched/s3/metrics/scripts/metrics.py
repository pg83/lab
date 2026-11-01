#!/usr/bin/env python3

import os
from pathlib import Path
import re
import tempfile
import time


OUTPUT = Path('/var/run/node_exporter/textfile/s3-volumes.prom')
LABEL = re.compile(r'S3_(HDD|STORE|LOAD)_([0-9]+)$|S3_(ETCD)$')


def mount_paths():
    found = {}
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = (proc / 'cmdline').read_bytes().split(b'\0')
            exe = args[0].rsplit(b'/', 1)[-1]
            if not (exe == b'etcd' or (exe == b's3' and args[1:2] == [b'cell'])):
                continue
            for line in (proc / 'mountinfo').read_text().splitlines():
                fields = line.split()
                mount = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), fields[4])
                found.setdefault(fields[2], proc / 'root' / mount.lstrip('/'))
        except (OSError, ValueError):
            continue
    return found


def collect():
    paths = mount_paths()
    lines = []
    kinds = {}

    def emit(name, value, labels=None, kind='gauge'):
        if name not in kinds:
            lines.append(f'# TYPE {name} {kind}')
            kinds[name] = kind
        def quote(value):
            return str(value).replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
        fields = ','.join(f'{key}="{quote(value)}"' for key, value in sorted((labels or {}).items()))
        lines.append(name + ('{' + fields + '}' if fields else '') + ' ' + str(value))

    for entry in sorted(Path('/sys/class/block').iterdir()):
        try:
            info = dict(line.split('=', 1) for line in (entry / 'uevent').read_text().splitlines())
            match = LABEL.fullmatch(info.get('PARTNAME', ''))
            if not match:
                continue
            role = (match[1] or match[3]).lower()
            index = match[2] if match[2] is not None else '-1'
            device = info['DEVNAME']
            disk = entry.resolve().parent.name
            mount = '' if role == 'hdd' else '/var/mnt/etcd_2' if role == 'etcd' else f'/var/run/s3_cell_{index}/{role}'
            labels = dict(role=role, cell_index=index, device=device, disk=disk, mount=mount)
            emit('s3_volume_info', 1, labels)
            stat = [int(v) for v in (entry / 'stat').read_text().split()]
            for name, value in [('read_operations', stat[0]), ('read_bytes', stat[2] * 512),
                                ('write_operations', stat[4]), ('write_bytes', stat[6] * 512)]:
                emit('s3_volume_' + name + '_total', value, labels, 'counter')
            if role == 'hdd':
                continue
            path = paths.get(info['MAJOR'] + ':' + info['MINOR'])
            success = 0
            if path is not None:
                try:
                    st = os.statvfs(path)
                    for name, value in [('capacity', st.f_blocks), ('used', st.f_blocks - st.f_bfree), ('free', st.f_bavail)]:
                        emit('s3_volume_' + name + '_bytes', value * st.f_frsize, labels)
                    success = 1
                except OSError:
                    pass
            emit('s3_volume_filesystem_success', success, labels)
        except (OSError, ValueError, KeyError, IndexError) as error:
            print(f's3 volumes: {entry.name}: {error}', flush=True)
    emit('s3_volume_collect_timestamp_seconds', time.time())
    return lines


def main():
    lines = collect()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='s3-volumes.', suffix='.tmp', dir=OUTPUT.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write('\n'.join(lines) + '\n')
        os.replace(tmp, OUTPUT)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


if __name__ == '__main__':
    main()
