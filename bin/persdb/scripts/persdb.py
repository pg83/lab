#!/usr/bin/env python3

"""
persdb — thin CLI over EFI variables via efi_get / efi_put. Replaces
the old HTTP service (ix_serve_persdb) plus its persdb_get /
persdb_put shims; one binary, no daemon, no TCP.

Must be run as root — efi_get / efi_put mount efivarfs inside an
unshare -m namespace and poke the UEFI variable table, both of
which need CAP_SYS_ADMIN.

Usage:
    persdb get <key>          prints raw bytes to stdout
    persdb put <path>         stores the file at <path> under key=<path>

The "key = file path" contract matches the old persdb_put: the dev
script stages /master.key on disk and says `persdb put /master.key`
so the EFI-variable name derives from that path.
"""

import sys
import hashlib
import subprocess


UUID = 'f299ef14-61d1-4bf0-bfbc-565af88df0c9'


def hash_key(key):
    return hashlib.md5(key.encode()).hexdigest()


def get(key):
    # efi_get emits a 4-byte EFI attribute prefix before the payload —
    # strip it like the old HTTP server did.
    return subprocess.check_output([
        'unshare', '-m', 'efi_get', hash_key(key), UUID,
    ])[4:]


def put(path):
    subprocess.check_call([
        'unshare', '-m', 'efi_put', hash_key(path), UUID, path,
    ])


def main():
    cmd = sys.argv[1]
    arg = sys.argv[2]

    if cmd == 'get':
        sys.stdout.buffer.write(get(arg))
    elif cmd == 'put':
        put(arg)
    else:
        sys.exit(f'persdb: unknown command {cmd!r}')


if __name__ == '__main__':
    main()
