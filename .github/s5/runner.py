#!/usr/bin/env python3

import argparse
import asyncio
import contextlib
import os
from pathlib import Path
import pwd
import shlex
import signal
import subprocess
import tempfile


# Xiaomi: each external TCP port forwards to eth0:8058 on that lab.
LABS = {
    'lab1': ('5.188.103.251', 8058),
    'lab2': ('5.188.103.251', 8059),
    'lab3': ('5.188.103.251', 8060),
}


def setup(directory):
    try:
        user = pwd.getpwnam('s5')
    except KeyError:
        subprocess.run([
            'useradd', '--create-home', '--shell', '/bin/sh', '--password', '*', 's5',
        ], check=True)
        user = pwd.getpwnam('s5')

    ssh = Path(user.pw_dir) / '.ssh'
    ssh.mkdir(mode=0o700, exist_ok=True)
    ssh.chmod(0o700)
    os.chown(ssh, user.pw_uid, user.pw_gid)
    authorized = ssh / 'authorized_keys'
    authorized.write_bytes((Path(__file__).with_name('authorized_keys')).read_bytes())
    authorized.chmod(0o600)
    os.chown(authorized, user.pw_uid, user.pw_gid)
    Path('/run/sshd').mkdir(mode=0o755, exist_ok=True)

    host_key = directory / 'host_key'
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(host_key)], check=True)
    config = directory / 'sshd_config'
    config.write_text(f'''HostKey {host_key}
AuthorizedKeysFile .ssh/authorized_keys
AllowUsers s5
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
AuthenticationMethods publickey
AllowTcpForwarding local
AllowAgentForwarding no
X11Forwarding no
PermitTTY no
MaxSessions 0
GatewayPorts no
UsePAM no
LoginGraceTime 30
ClientAliveInterval 30
ClientAliveCountMax 3
LogLevel VERBOSE
''')
    subprocess.run(['/usr/sbin/sshd', '-t', '-f', str(config)], check=True)
    return config


async def connect(name, host, port, config):
    command = shlex.join(['/usr/sbin/sshd', '-i', '-e', '-f', str(config)])
    while True:
        print(f'{name}: connecting to {host}:{port}', flush=True)
        process = await asyncio.create_subprocess_exec(
            'socat', '-d', '-d',
            f'TCP4:{host}:{port},connect-timeout=10,keepalive,keepidle=30,keepintvl=10,keepcnt=3',
            f'EXEC:{command}',
            start_new_session=True,
        )
        try:
            status = await process.wait()
            print(f'{name}: disconnected (exit {status}); retry in 5s', flush=True)
        finally:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
        await asyncio.sleep(5)


async def run(config, lab, port_offset=0, duration=0):
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    async with asyncio.TaskGroup() as group:
        labs = LABS if lab == 'all' else {lab: LABS[lab]}
        tasks = [group.create_task(connect(name, host, port + port_offset, config))
                 for name, (host, port) in labs.items()]
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=duration or None)
        for task in tasks:
            task.cancel()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Connect labs to this runner over SSH.')
    parser.add_argument('lab', choices=[*LABS, 'all'])
    parser.add_argument('--port-offset', type=int, default=0)
    parser.add_argument('--duration', type=int, default=0, help='Stop after this many seconds; 0 runs until cancelled.')
    args = parser.parse_args()
    if args.duration < 0 or any(not 1 <= port + args.port_offset <= 65535 for _, port in LABS.values()):
        parser.error('invalid duration or port offset')
    with tempfile.TemporaryDirectory(prefix='s5-') as directory:
        asyncio.run(run(setup(Path(directory)), args.lab, args.port_offset, args.duration))
