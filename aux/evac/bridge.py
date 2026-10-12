#!/usr/bin/env python3
"""Connect lab OpenVPN management to a macOS Keychain signer over SSH.

Only certificate/signature requests go to the Mac; VPN packets stay on lab.
Start OpenVPN with management-hold and a Unix management socket in a protected directory.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import secrets
import signal
import sys


def prepare_signature(encoded, algorithm):
    """Encode OpenSSL 3 PSS requests for the Keychain's raw RSA operation.

    EMSA-PSS-ENCODE from RFC 8017 section 9.1.1; configured key is RSA-2048.
    Private-key operations remain on the Mac.
    """
    parts = algorithm.split(',')
    if parts[0] in {'RSA_NO_PADDING', 'RSA_PKCS1_PADDING'} and len(parts) == 1:
        return encoded, algorithm
    if parts[0] != 'RSA_PKCS1_PSS_PADDING':
        raise ValueError('Unsupported OpenVPN signature algorithm')
    params = dict(part.split('=', 1) for part in parts[1:])
    if set(params) != {'hashalg', 'saltlen'} or len(parts) != 3:
        raise ValueError('Unsupported PSS parameters')
    hashes = {'SHA256': hashlib.sha256, 'SHA384': hashlib.sha384, 'SHA512': hashlib.sha512}
    digest = hashes[params['hashalg']]
    message_hash = base64.b64decode(encoded, validate=True)
    hlen = digest().digest_size
    if len(message_hash) != hlen:
        raise ValueError('PSS hash has wrong length')
    emlen = 256
    salt_lengths = {'digest': hlen, 'max': emlen - hlen - 2}
    salt = secrets.token_bytes(salt_lengths[params['saltlen']])
    h = digest(b'\0' * 8 + message_hash + salt).digest()
    db = b'\0' * (emlen - hlen - len(salt) - 2) + b'\x01' + salt
    mask = b''.join(digest(h + i.to_bytes(4, 'big')).digest()
                    for i in range((len(db) + hlen - 1) // hlen))
    masked = bytearray(a ^ b for a, b in zip(db, mask))
    masked[0] &= 0x7f  # emBits = modulusBits - 1 = 2047.
    result = bytes(masked) + h + b'\xbc'
    return base64.b64encode(result).decode(), 'RSA_NO_PADDING'


async def run(args):
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, asyncio.current_task().cancel)
    common = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
              '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3']
    ui_flag = '' if args.allow_keychain_ui else '--no-ui '
    signer_command = [*common, '-o', 'IdentitiesOnly=yes', '-o',
                      f'UserKnownHostsFile={args.known_hosts}', '-i', args.key,
                      '-J', args.lab, '-p', str(args.mac_port), args.mac,
                      f'{args.helper} --cn {args.cn} {ui_flag}serve']
    # All remote shell arguments here are fixed local configuration, not server input.
    signer = await asyncio.create_subprocess_exec(*signer_command,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
    management = None

    async def request(value):
        signer.stdin.write((json.dumps(value) + '\n').encode())
        await signer.stdin.drain()
        line = await asyncio.wait_for(signer.stdout.readline(), 120 if args.allow_keychain_ui else 20)
        if not line:
            raise RuntimeError('Keychain signer disconnected')
        result = json.loads(line)
        if 'error' in result:
            raise RuntimeError('Keychain: ' + result['error'])
        return result

    try:
        certificate = (await request({'op': 'cert'}))['certificate']
        if not certificate.startswith('-----BEGIN CERTIFICATE-----\n'):
            raise RuntimeError('Signer did not provide a PEM certificate')
        management = await asyncio.create_subprocess_exec(
            *common, args.lab, '/srv/evac-vpn/socket-relay /srv/evac-vpn/management.sock',
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)

        async def send(text):
            management.stdin.write(text.encode())
            await management.stdin.drain()

        await send('version 3\nstate on\nhold off\nhold release\n')
        while raw := await management.stdout.readline():
            line = raw.decode().strip()
            if line.startswith('>NEED-CERTIFICATE:'):
                await send('certificate\n' + certificate + 'END\n')
                print('Certificate supplied from Keychain', flush=True)
            elif line.startswith('>PK_SIGN:'):
                payload, sep, algorithm = line[len('>PK_SIGN:'):].partition(',')
                if not sep:
                    raise RuntimeError('Unsupported OpenVPN signature algorithm')
                payload, algorithm = prepare_signature(payload, algorithm)
                signed = await request({'op': 'sign', 'data': payload, 'algorithm': algorithm})
                signature = signed['signature']
                if not isinstance(signature, str) or '\n' in signature:
                    raise RuntimeError('Invalid signature response')
                await send('pk-sig\n' + signature + '\nEND\n')
                print('TLS handshake signed on Mac', flush=True)
            elif line.startswith(('>FATAL:', 'ERROR:', '>PASSWORD:')):
                # A password notification can contain an auth token: do not log it.
                raise RuntimeError('OpenVPN requires attention; inspect its protected log')
            elif line.startswith('>STATE:'):
                print(line, flush=True)
        raise RuntimeError('OpenVPN management connection closed')
    finally:
        if management and management.returncode is None:
            try:
                management.stdin.write(b'signal SIGTERM\n')
                await management.stdin.drain()
                management.stdin.close()
                await asyncio.wait_for(management.wait(), 3)
            except (BrokenPipeError, ConnectionResetError, asyncio.TimeoutError):
                pass
        for process in (management, signer):
            if process and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key', required=True)
    parser.add_argument('--known-hosts', required=True)
    parser.add_argument('--lab', default='root@lab1.mesh')
    parser.add_argument('--mac', default='pg@10.0.0.248')
    parser.add_argument('--mac-port', type=int, default=12345)
    parser.add_argument('--cn', default='pg@ld.yandex.ru')
    parser.add_argument('--helper', default='/Users/pg/.local/libexec/evac/evac-keychain-signer')
    parser.add_argument('--allow-keychain-ui', action='store_true', help='Allow the initial Keychain permission dialog')
    args = parser.parse_args()
    # These values are inserted in an SSH remote command; reject shell syntax.
    import re
    for value in (args.cn, args.helper):
        if not re.fullmatch(r'[a-zA-Z0-9_@./+-]+', value):
            parser.error('Unsupported characters in helper path or certificate name')
    try:
        asyncio.run(run(args))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
