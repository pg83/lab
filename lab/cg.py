#!/usr/bin/env python3

import io
import os
import sys
import ast
import zlib
import time
import json
import types
import shutil
import pickle
import base64
import random
import hashlib
import contextlib
import subprocess
import collections

import urllib.request as ur


DISABLE_ALL = [
    #'drop_bear_2',
    'co2_mon',  # USB HID device absent; crash-loops with "hid_open: error"
    'gofra2',
]

DISABLE = {
    'lab1': DISABLE_ALL + [],
    'lab2': DISABLE_ALL + [],
    'lab3': DISABLE_ALL + [],
}

# Allow-list for SamogonBot. Empty → crash-loop (no world-writable bot).
TG_ALLOW_USERS = '51154499'

CPUS_PER_SLOT = 4

HOST_CPUS = {
    'lab1': 88,
    'lab2': 80,
    'lab3': 56,
}

GORN_N = {h: c // CPUS_PER_SLOT for h, c in HOST_CPUS.items()}

SSH_TUNNELS = [
    {
        'key': 'ssh_jopa_tunnel',
        'keyn': '/tunnel/ssh_ampere_tunnel',
        'addr': 'mudak@45.11.171.78',
        'port': 22,
        'tout': 600,
    },
    {
        'key': 'ssh_cz_tunnel',
        'keyn': '/tunnel/ssh_cz_tunnel',
        'addr': 'root@176.74.218.69',
        'port': 22,
        'tout': 600,
    },
]


@contextlib.contextmanager
def memfd(name):
    fd = os.memfd_create(name, flags=0)

    try:
        yield f'/proc/self/fd/{fd}'
    finally:
        os.close(fd)


@contextlib.contextmanager
def multi(*args):
    with contextlib.ExitStack() as es:
        yield (es.enter_context(a) for a in args)


class IPerf:
    def __init__(self, port):
        self.port = port

    def pkgs(self):
        yield {
            'pkg': 'bin/iperf',
        }

    def run(self):
        exec_into('iperf', '-s', '-p', self.port)


class IPerf3:
    def __init__(self, port):
        self.port = port

    def pkgs(self):
        yield {
            'pkg': 'bin/iperf/3',
        }

    def run(self):
        # Override TMPDIR: default ${PWD} is root-owned, iperf3 mkstemp EACCES.
        exec_into('iperf3', '-s', '-p', self.port, TMPDIR='/var/run/i_perf_3')


class Heat:
    def __init__(self, num):
        self.uniq = num

    def run(self):
        exec_into('timeout', '100s', 'nice', '-n', '20', 'md5sum', '/dev/zero')

    def name(self):
        return f'heat_{self.uniq}'

    def users(self):
        return [
            self.name(),
        ]


class NodeExporter:
    def __init__(self, port):
        self.port = port

    def pkgs(self):
        yield {
            'pkg': 'bin/prometheus/node/exporter',
        }

    def prom_port(self):
        return self.port

    def run(self):
        exec_into('node_exporter', f'--web.listen-address=127.0.0.1:{self.port}')


def make_dirs(path, owner=None):
    os.makedirs(path, exist_ok=True)

    if owner:
        shutil.chown(path, user=owner, group=owner)


class Collector:
    def __init__(self, port, host):
        self.port = port
        self.host = host
        self.jobs = []

    def prom_port(self):
        return self.port

    def pkgs(self):
        yield {
            'pkg': 'bin/prometheus',
        }

    def config(self):
        return {
            'global': {
                'scrape_interval': '15s',
                'evaluation_interval': '15s',
                # Federation: per-host origin; else federator dedupes series.
                'external_labels': {'host': self.host},
            },
            'scrape_configs': self.jobs,
        }

    def prepare(self):
        srv = Service(self)
        make_dirs(srv.home_dir(), owner=srv.user())

    def run(self):
        with memfd('prometheus.conf') as fn:
            with open(fn, "w") as f:
                f.write(json.dumps(self.config(), sort_keys=True, indent=4))

            args = [
                'prometheus',
                f'--config.file={fn}',
                '--storage.tsdb.path=/home/collector/',
                # 0.0.0.0: prom 3.7 repeated --listen flag drops 2nd arg.
                f'--web.listen-address=0.0.0.0:{self.port}',
            ]

            exec_into(*args)


NEBULA = {
    'punchy': {
        'punch': True,
    },
    'relay': {
        'am_relay': False,
        'use_relays': False,
    },
    'logging': {
        'level': 'info',
        'format': 'text',
    },
    'firewall': {
        'outbound_action': 'drop',
        'inbound_action': 'drop',
        'conntrack': {
            'tcp_timeout': '12m',
            'udp_timeout': '3m',
            'default_timeout': '10m',
        },
        'outbound': [
            {
                'port': 'any',
                'proto': 'any',
                'host': 'any',
            },
        ],
        'inbound': [
            {
                'port': 'any',
                'proto': 'any',
                'host': 'any',
            },
        ],
    },
    'stats': {
        'type': 'prometheus',
        'path': '/metrics',
        'namespace': 'nebula',
        'subsystem': 'nebula',
        'interval': '10s',
        'message_metrics': True,
        'lighthouse_metrics': True,
    },
}


def get_key(k):
    return ur.urlopen('http://localhost:8022' + k).read()


def get_key_v2(k):
    # Opt-in v2 sibling; no fallback to v1 to avoid hiding v2 bugs.
    return ur.urlopen('http://localhost:8034' + k).read()


class Nebula:
    def pkgs(self):
        yield {
            'pkg': 'bin/nebula/daemon',
        }

    def run(self):
        with multi(memfd("conf"), memfd("ca"), memfd("cert"), memfd("key")) as (conf, ca, cert, key):
            cfg = self.config()

            cfg['static_host_map'] = self.smap

            # 8MB sock bufs need net.core.{r,w}mem_max≥8M or clamps silently.
            cfg['listen'] = {
                'host': '0.0.0.0',
                'port': self.port,
                'read_buffer': 8 * 1024 * 1024,
                'write_buffer': 8 * 1024 * 1024,
                'routines': 2,
                'batch': 128,
            }

            cfg['pki'] = {
                'ca': ca,
                'cert': cert,
                'key': key,
            }

            cfg['stats']['listen'] = '127.0.0.1:' + str(self.prom_port())

            with open(conf, "w") as f:
                f.write(json.dumps(cfg, indent=4, sort_keys=True))

            with open(ca, 'wb') as f:
                f.write(get_key_v2('/nebula/ca.crt'))

            with open(cert, 'wb') as f:
                f.write(get_key_v2(f'/nebula/{self.host}.crt'))

            with open(key, 'wb') as f:
                f.write(get_key_v2(f'/nebula/{self.host}.key'))

            exec_into('nebula', '--config', conf)


class NebulaNode(Nebula):
    def __init__(self, host, port, smap, prom, advr, self_vip):
        self.host = host
        self.port = port
        self.smap = smap
        self.prom = prom
        self.advr = advr
        self.self_vip = self_vip

    def run(self):
        # Strip self-entry; run-time filter so smap is fully populated.
        self.smap = {k: v for k, v in self.smap.items() if k != self.self_vip}
        super().run()

    def prom_port(self):
        return self.prom

    def user(self):
        return 'root'

    def iter_upnp(self):
        for h, p, ep in self.iter_upnp_3():
            yield {
                'addr': h,
                'port': p,
                'ext_port': ep,
                'proto': 'UDP',
            }

    def iter_upnp_3(self):
        for r in self.advr:
            h, p = r.split(':')

            yield (h, int(p), int(p) + int(h.split('.')[-1]))

    def extra_advr(self):
        return [f'5.188.103.251:{ep}' for h, p, ep in self.iter_upnp_3()]

    def config(self):
        cfg = json.loads(json.dumps(NEBULA))

        cfg['tun'] = {
            'disabled': False,
            'dev': 'nebula0',
            'drop_local_broadcast': False,
            'drop_multicast': False,
            'tx_queue': 500,
            'mtu': 1300,
        }

        cfg['lighthouse'] = {
            'am_lighthouse': False,
            'interval': 60,
            'hosts': list(self.smap.keys()),
            'advertise_addrs': self.advr + self.extra_advr(),
        }

        return cfg


class NebulaLh(Nebula):
    def __init__(self, host, port, smap, prom, pmap):
        self.host = host
        self.port = port
        self.smap = smap
        self.prom = prom
        self.pmap = pmap

    def iter_upnp_3(self):
        yield self.pmap

    def iter_upnp(self):
        for h, p, ep in self.iter_upnp_3():
            yield {
                'addr': h,
                'port': p,
                'ext_port': ep,
                'proto': 'UDP',
            }

    def prom_port(self):
        return self.prom;

    def config(self):
        cfg = json.loads(json.dumps(NEBULA))

        cfg['tun'] = {
            'disabled': True,
        }

        cfg['lighthouse'] = {
            'am_lighthouse': True,
        }

        return cfg


class Gofra:
    # Multipath UDP encap. Overlay 192.168.103.0/24, TUN gofra0.
    def __init__(self, host, port, hosts, vip):
        self.host = host
        self.port = port
        self.hosts = hosts
        self.vip = vip

    def name(self):
        return 'gofra'

    def user(self):
        return 'root'

    def users(self):
        return ['root', 'gofra']

    def pkgs(self):
        yield {'pkg': 'bin/gofra/2'}
        yield {'pkg': 'bin/sched/hugepages', 'delay': '10'}

    def ini(self):
        lines = []
        lines.append('[me]')
        lines.append('vip     = ' + self.vip)
        lines.append('tun_dev = gofra0')
        lines.append('tun_mtu = 1400')
        lines.append('user    = gofra')
        lines.append('')
        lines.append('[peers]')
        for vip, underlays in sorted(self.hosts.items()):
            eps = ', '.join(f'{u}:{self.port}' for u in underlays)
            lines.append(f'{vip} = {eps}')
        lines.append('')
        lines.append('[udp]')
        lines.append('recv_buf = 16777216')
        lines.append('send_buf = 16777216')
        lines.append('')
        lines.append('[probe]')
        lines.append('timeout_ms = 2000')
        return '\n'.join(lines) + '\n'

    def run(self):
        with memfd('config.ini') as conf:
            with open(conf, 'w') as f:
                f.write(self.ini())
            exec_into('nice', '-n', '-20', 'gofra', '--config', conf)


class Gofra2:
    # Staging twin: overlay 192.168.104.0/24, TUN gofra1, port 8051.
    def __init__(self, host, port, hosts, vip):
        self.host = host
        self.port = port
        self.hosts = hosts
        self.vip = vip

    def name(self):
        return 'gofra2'

    def user(self):
        return 'root'

    def users(self):
        return ['root', 'gofra2']

    def pkgs(self):
        yield {'pkg': 'bin/gofra/staging'}

    def ini(self):
        lines = []
        lines.append('[me]')
        lines.append('vip     = ' + self.vip)
        lines.append('tun_dev = gofra1')
        lines.append('tun_mtu = 1400')
        lines.append('user    = gofra2')
        lines.append('')
        lines.append('[peers]')
        for vip, underlays in sorted(self.hosts.items()):
            eps = ', '.join(f'{u}:{self.port}' for u in underlays)
            lines.append(f'{vip} = {eps}')
        lines.append('')
        lines.append('[udp]')
        lines.append('recv_buf = 16777216')
        lines.append('send_buf = 16777216')
        lines.append('')
        lines.append('[probe]')
        lines.append('timeout_ms = 2000')
        return '\n'.join(lines) + '\n'

    def run(self):
        with memfd('config.ini') as conf:
            with open(conf, 'w') as f:
                f.write(self.ini())
            exec_into('nice', '-n', '-20', 'gofra-staging', '--config', conf)


class Ssh3:
    def __init__(self, port):
        self.port = port

    def user(self):
        return 'root'

    def pkgs(self):
        yield {
            'pkg': 'bin/ssh/3',
        }

    def run(self):
        args = [
            'ssh3-server',
            '-bind', f'0.0.0.0:{self.port}',
            '-cert', '/etc/keys/ssh3_cert.pem',
            '-key', '/etc/keys/ssh3_priv.key',
            '-url-path', '/',
        ]

        exec_into(*args, SSH3_LOG_FILE='/proc/self/fd/1')


HA_CONF = '''
global
    maxconn 100

defaults
    timeout connect 1ms
    timeout client 50000
    timeout server 50000

listen socks5
    bind 127.0.0.1:{port}
    mode tcp
    balance roundrobin
    retries 10
    option redispatch
'''


def haproxy_conf_parts(port, addrs):
    yield HA_CONF.replace('{port}', str(port))

    for n, addr in enumerate(addrs):
        yield f'    server server{n} {addr} check'


class SocksProxy:
    def __init__(self, port, addrs):
        self.v = HA_CONF
        self.p = port
        self.a = addrs
        self.t = 400

    def pkgs(self):
        yield {
            'pkg': 'bin/haproxy/ext',
        }

    def conf(self):
        return '\n'.join(haproxy_conf_parts(self.p, self.a)).strip() + '\n'

    def run(self):
        with memfd('haproxy.conf') as path:
            with open(path, 'w') as f:
                f.write(self.conf())

            tout = int((random.random() + 0.5) * self.t)

            exec_into('timeout', f'{tout}s', 'haproxy', '-f', path)


class SshTunnel:
    def __init__(self, port, addr, keyn, user, rport, tout):
        self.port = port
        self.addr = addr
        self.keyn = keyn
        self._usr = user
        self.rport = rport
        self.tout = tout

    def name(self):
        return self._usr

    def pkgs(self):
        yield {
            'pkg': 'bin/openssh/client',
        }

    def run(self):
        try:
            os.unlink('key')
        except Exception:
            pass

        with open('key', 'wb') as f:
            f.write(get_key(self.keyn))

        os.chmod('key', 0o400)

        tout = int((random.random() + 0.5) * self.tout)

        args = [
            'timeout', str(tout) + 's',
            'ssh', '-q',
            '-p', str(self.rport),
            '-o', 'StrictHostKeyChecking no',
            '-i', 'key',
            '-D', self.port,
            '-N',
            self.addr,
        ]

        exec_into(*args)


class SftpD:
    def __init__(self, port, path):
        self.port = port
        self.path = path

    def users(self):
        return ['root', 'sftp_d']

    def pkgs(self):
        yield {
            'pkg': 'bin/sftp/go/patched',
        }

    def run(self):
        with multi(memfd("conf"), memfd("rsa"), memfd("ecdsa"), memfd("ed")) as (conf, rsa, ecdsa, ed):
            cfg = {
                'sftpd': {
                    'host_keys': [rsa, ecdsa, ed],
                },
            }

            with open(conf, 'w') as f:
                f.write(json.dumps(cfg, indent=4,sort_keys=True))

            with open(rsa, 'w') as f:
                f.write(open('/etc/keys/ssh_rsa').read())

            with open(ecdsa, 'w') as f:
                f.write(open('/etc/keys/ssh_ecdsa').read())

            with open(ed, 'w') as f:
                f.write(open('/etc/keys/ssh_ed25519').read())

            args = [
                'sftpgo', 'portable',
                '--config-file', conf,
                '--s3-bucket', self.path,
                '--s3-endpoint', 'http://127.0.0.1:8012/',
                '--s3-region', 'minio',
                '--s3-access-key', get_key('/s3/iam/geesefs/key').decode().strip(),
                '--s3-access-secret', get_key('/s3/iam/geesefs/secret').decode().strip(),
                '--password', 'qwerty123',
                '--username', 'anon',
                '--sftpd-port', str(self.port),
                '--fs-provider', 's3fs',
                '--s3-force-path-style',
                '--s3-skip-tls-verify',
                '--log-level', 'debug',
                '--log-file-path', '/dev/stdout',
            ]

            exec_into(*args, user=self.users()[1])


MINIO_SCRIPT = '''
set -xue

mkdir -p /var/mnt/minio/1
mount -t xfs LABEL=MINIO_1 /var/mnt/minio/1
mkdir -p /var/mnt/minio/1/data

mkdir -p /var/mnt/minio/2
mount -t xfs LABEL=MINIO_2 /var/mnt/minio/2
mkdir -p /var/mnt/minio/2/data

mkdir -p /var/mnt/minio/3
mount -t xfs LABEL=MINIO_3 /var/mnt/minio/3
mkdir -p /var/mnt/minio/3/data

exec su-exec minio minio server --address {ipv4}:{port} {cmap}
'''


class MinIO:
    def __init__(self, ipv4, port, cmap):
        self.v = MINIO_SCRIPT
        self.ipv4 = ipv4
        self.port = port
        self.cmap = cmap
        self.script = MINIO_SCRIPT

    @property
    def addr(self):
        return f'{self.ipv4}:{self.port}'

    def name(self):
        return 'minio'

    def users(self):
        return ['root', 'minio']

    def pkgs(self):
        yield {
            'pkg': 'bin/minio/daemon',
        }

        yield {
            'pkg': 'bin/su/exec',
        }

    def run(self):
        s = self.script

        s = s.replace('{port}', str(self.port))
        s = s.replace('{cmap}', self.cmap)
        s = s.replace('{ipv4}', self.ipv4)

        with memfd('script') as ss:
            with open(ss, 'w') as f:
                f.write(s)

            args = [
                '/bin/unshare', '-m',
                '/bin/sh', ss
            ]

            kwargs = {
                'MINIO_ROOT_USER': get_key('/s3/user').decode().strip(),
                'MINIO_ROOT_PASSWORD': get_key('/s3/password').decode().strip(),
                'MINIO_BROWSER': 'off',
                'MINIO_PROMETHEUS_AUTH_TYPE': 'public',
            }

            exec_into(*args, **kwargs)

    def prom_jobs(self):
        yield {
            'job_name': self.name(),
            'metrics_path': '/minio/v2/metrics/cluster',
            'static_configs': [{'targets': [self.addr]}],
        }


class MinioConsole:
    def __init__(self, host, port, server):
        self.host = host
        self.port = port
        self.server = server

    def pkgs(self):
        yield {
            'pkg': 'bin/minio/console',
        }

    def run(self):
        args = [
            'minio-console',
            'server',
            '--host',
            self.host,
            '--port',
            self.port,
        ]

        exec_into(*args, CONSOLE_MINIO_SERVER=self.server)


DB_PREPARE = '''
set -xue
mkdir -p /home/root/.ssh
chmod 0700 /home/root/.ssh
cp /etc/sudo/authorized_keys /home/root/.ssh/
'''


class DropBear:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.script = DB_PREPARE

    def user(self):
        return 'root'

    def pkgs(self):
        yield {
            'pkg': 'bin/dropbear/2024',
        }

    def run(self):
        subprocess.run(['/bin/sh'], input=self.script.encode())

        with memfd('pid') as pid:
            args = [
                'dropbear',
                '-p', f'{self.host}:{self.port}',
                '-s', '-e', '-E', '-F',
                '-P', pid,
                '-r', '/etc/keys/dss',
                '-r', '/etc/keys/rsa',
                '-r', '/etc/keys/ecdsa',
                '-r', '/etc/keys/ed25519',
            ]

            exec_into(*args)


class DropBear2(DropBear):
    def __init__(self, port):
        DropBear.__init__(self, '0.0.0.0', port)


class GornSsh:
    def __init__(self, uniq, host, port, nebula_host):
        self.uniq = uniq
        self.host = host
        self.port = port
        self.nebula_host = nebula_host

    def name(self):
        return f'gorn_{self.uniq}'

    def user(self):
        return 'root'

    def users(self):
        return ['root']

    def std_dir(self):
        return f'/var/run/{self.name()}/std'

    def pkgs(self):
        yield {
            'pkg': 'bin/dropbear/2024',
        }

        yield {
            'pkg': 'bin/su/exec',
        }

        yield {
            'pkg': 'etc/lab/user/home',
            'user': self.name(),
            'user_home': self.home_dir(),
        }

    def home_dir(self):
        return f'/var/run/{self.name()}/home'

    def work_dir(self):
        return f'/var/run/{self.name()}/work'

    def prepare(self):
        u = self.name()
        make_dirs(self.home_dir(), owner=u)
        ssh_dir = f'{self.home_dir()}/.ssh'
        make_dirs(ssh_dir, owner=u)
        os.chmod(ssh_dir, 0o700)
        make_dirs(self.work_dir(), owner=u)

    def run(self):
        u = self.name()
        ak = f'{self.home_dir()}/.ssh/authorized_keys'

        with open(ak, 'wb') as f:
            f.write(get_key(f'/gorn/{self.nebula_host}.{u}.pub'))

        os.chmod(ak, 0o600)
        shutil.chown(ak, user=u, group=u)

        with multi(memfd('pid'), memfd('dss'), memfd('rsa'), memfd('ecdsa'), memfd('ed25519')) as (pid, dss, rsa, ecdsa, ed25519):
            for src, dst in [
                ('/etc/keys/dss', dss),
                ('/etc/keys/rsa', rsa),
                ('/etc/keys/ecdsa', ecdsa),
                ('/etc/keys/ed25519', ed25519),
            ]:
                with open(src, 'rb') as sf, open(dst, 'wb') as df:
                    df.write(sf.read())

            args = [
                'dropbear',
                '-p', f'{self.host}:{self.port}',
                '-s', '-e', '-E', '-F',
                '-P', pid,
                '-r', dss,
                '-r', rsa,
                '-r', ecdsa,
                '-r', ed25519,
            ]

            exec_into(*args, user=u)


class GornBase:
    def user(self):
        return 'root'

    def users(self):
        return ['root']

    def std_dir(self):
        return f'/var/run/{self.name()}/std'

    def home_dir(self):
        return f'{self.std_dir()}/home'

    def pkgs(self):
        yield {
            'pkg': 'bin/gorn',
        }

        yield {
            'pkg': 'bin/su/exec',
        }

        yield {
            'pkg': 'etc/lab/user/home',
            'user': self.name(),
            'user_home': self.home_dir(),
        }

    def prepare(self):
        u = self.name()
        make_dirs(self.home_dir(), owner=u)
        ssh_dir = f'{self.home_dir()}/.ssh'
        make_dirs(ssh_dir, owner=u)
        os.chmod(ssh_dir, 0o700)

    def base_config(self):
        eps = []

        for e in self.endpoints:
            eps.append({
                'host': e['host'],
                'port': e['port'],
                'user': e['user'],
                'path': e['path'],
                'log_path': e['log_path'],
                'ssh_key': get_key(f"/gorn/{e['nebula_host']}.{e['user']}.priv").decode(),
            })

        return {
            'endpoints': eps,
            'hosts': {
                ep['host']: {'cpus_per_slot': CPUS_PER_SLOT}
                for ep in self.endpoints
            },
            'etcd': {
                'endpoints': list(self.etcd_endpoints),
            },
            's3': {
                'endpoint': self.s3['endpoint'],
                'region': self.s3['region'],
                'bucket': self.s3['bucket'],
                'access_key': get_key('/s3/iam/gorn/key').decode().strip(),
                'secret_key': get_key('/s3/iam/gorn/secret').decode().strip(),
                'use_path_style': self.s3.get('use_path_style', True),
            },
        }

    def run(self):
        cfg = self.config()

        with memfd('conf') as fn:
            with open(fn, 'w') as f:
                f.write(json.dumps(cfg))

            exec_into(
                'gorn', self.subcommand(), '--config', fn,
                user=self.name(),
                PATH='/bin',
                ETCDCTL_ENDPOINTS=','.join(self.etcd_endpoints),
            )


class Gorn(GornBase):
    def __init__(self, endpoints, s3, etcd_endpoints):
        self.endpoints = endpoints
        self.s3 = s3
        self.etcd_endpoints = list(etcd_endpoints)

    def name(self):
        return 'gorn'

    def subcommand(self):
        return 'serve'

    def config(self):
        return self.base_config()


class GornCtl(GornBase):
    def __init__(self, endpoints, s3, listen, etcd_endpoints):
        self.endpoints = endpoints
        self.s3 = s3
        self.listen = listen
        self.etcd_endpoints = list(etcd_endpoints)

    def name(self):
        return 'gorn_ctl'

    def subcommand(self):
        return 'control'

    def config(self):
        cfg = self.base_config()
        cfg['control'] = {'listen': self.listen}
        return cfg


class GornCtlNebula(GornCtl):
    def name(self):
        return 'gorn_ctl_nb'


class GornProm(GornBase):
    def __init__(self, endpoints, s3, port, etcd_endpoints):
        self.endpoints = endpoints
        self.s3 = s3
        self.port = port
        self.etcd_endpoints = list(etcd_endpoints)

    def name(self):
        return 'gorn_prom'

    def subcommand(self):
        return 'prom'

    def config(self):
        cfg = self.base_config()
        cfg['prom'] = {'listen': f'127.0.0.1:{self.port}'}
        return cfg

    def prom_port(self):
        return self.port


class GornWeb:
    def __init__(self, api, listen):
        self.api = api
        self.listen = listen

    def name(self):
        return 'gorn_web'

    def pkgs(self):
        yield {
            'pkg': 'bin/gorn',
        }

    def run(self):
        cfg = {
            'web': {
                'api': self.api,
                'listen': self.listen,
            },
        }

        with memfd('conf') as fn:
            with open(fn, 'w') as f:
                f.write(json.dumps(cfg))

            exec_into('gorn', 'web', '--config', fn, PATH='/bin')


class MolotWeb:
    # Per-run ledger browser. One per host; reach via <host>.nebula:port.
    def __init__(self, listen, gorn_api, s3_endpoint, s3_bucket):
        self.listen = listen
        self.gorn_api = gorn_api
        self.s3_endpoint = s3_endpoint
        self.s3_bucket = s3_bucket

    def name(self):
        return 'molot_web'

    def pkgs(self):
        yield {
            'pkg': 'bin/molot',
        }

    def run(self):
        aws_key = get_key('/s3/iam/molot/key').decode().strip()
        aws_secret = get_key('/s3/iam/molot/secret').decode().strip()

        exec_into(
            'molot', 'web',
            '--listen', self.listen,
            GORN_API=self.gorn_api,
            S3_ENDPOINT=self.s3_endpoint,
            S3_BUCKET=self.s3_bucket,
            AWS_ACCESS_KEY_ID=aws_key,
            AWS_SECRET_ACCESS_KEY=aws_secret,
            PATH='/bin',
        )


SECOND_IP = '''
set -x
ip addr del {addr} dev eth0
exec etcdctl lock /lock/{name} -- /bin/sh -c "set -xue; ip addr add {addr} dev eth0; sleep 1000"
'''


class SecondIP:
    def __init__(self, addr, etcd_endpoints):
        self.addr = addr
        self.etcd_endpoints = list(etcd_endpoints)
        self.script = SECOND_IP

    def name(self):
        return 'ip_' + self.addr.replace('.', '_').replace('/', '_')

    def user(self):
        return 'root'

    def run(self):
        s = self.script
        s = s.replace('{addr}', self.addr)
        s = s.replace('{name}', self.name())

        with memfd('script') as fn:
            with open(fn, 'w') as f:
                f.write(s)

            exec_into(
                '/bin/sh', fn,
                ETCDCTL_ENDPOINTS=','.join(self.etcd_endpoints),
            )


class BalancerHttp:
    def __init__(self, port, mgmt_port, real):
        self.port = port
        self.mgmt_port = mgmt_port
        self.real = real

    def pkgs(self):
        yield {
            'pkg': 'bin/reproxy',
        }

    def prom_port(self):
        return self.mgmt_port

    def it_args(self):
        yield 'reproxy'
        yield f'--listen=0.0.0.0:{self.port}'
        yield '--mgmt.enabled'
        yield f'--mgmt.listen=127.0.0.1:{self.mgmt_port}'
        yield '--static.enabled'
        yield '--logger.enabled'
        yield '--logger.stdout'

        for x in self.real:
            yield f'--static.rule={x["server"]},{x["source"]},{x["dest"]}'

    def run(self):
        exec_into(*list(self.it_args()))


def it_nebula_reals(lh, h, port):
    yield lh['ip'], lh['port']

    for n in h['net']:
        yield n['ip'], port


class EtcdPrivate:
    def __init__(self, peers, port_peer, port_client, hostname, etcid, peer_addr, client_addr, user_name, cluster_state, data_dir=None):
        self.etcid = etcid
        self.peers = peers
        self.port_peer = port_peer
        self.port_client = port_client
        self.hostname = hostname
        self.peer_addr = peer_addr
        self.client_addr = client_addr
        self.user_name = user_name
        # `new` to bootstrap; flip to `existing` once all members are up.
        self.cluster_state = cluster_state
        # tmpfs override for etcd_3; only safe restart is cold-start of all 3.
        self._data_dir = data_dir

    def name(self):
        return self.user_name

    def user(self):
        return self.user_name

    def prepare(self):
        if self._data_dir is None:
            make_dirs(f'/home/{self.user_name}', owner=self.user_name)

    def pkgs(self):
        yield {
            'pkg': 'bin/etcd/server',
        }

    @property
    def data_dir(self):
        return self._data_dir or f'/home/{self.user_name}/{self.etcid}'

    def it_all(self):
        for x in self.peers:
            yield f'{x["hostname"]}=http://{x["ip"]}:{self.port_peer}'

    def prom_jobs(self):
        yield {
            'job_name': self.name(),
            'static_configs': [{'targets': [f'{self.client_addr}:{self.port_client}']}],
        }

    def run(self):
        os.makedirs(self.data_dir, exist_ok=True)

        if 'ETCDCTL_ENDPOINTS' in os.environ:
            os.environ.pop('ETCDCTL_ENDPOINTS')

        args = [
            'etcd',
            '--name', self.hostname,
            '--data-dir', self.data_dir,
            '--initial-advertise-peer-urls',
            f'http://{self.peer_addr}:{self.port_peer}',
            '--listen-peer-urls',
            f'http://{self.peer_addr}:{self.port_peer}',
            '--listen-client-urls',
            f'http://{self.client_addr}:{self.port_client}',
            '--advertise-client-urls',
            f'http://{self.client_addr}:{self.port_client}',
            '--initial-cluster-token',
            self.etcid,
            '--initial-cluster',
            ','.join(self.it_all()),
            '--initial-cluster-state',
            self.cluster_state,
            # 1h MVCC retention keeps live set under 2GiB during long builds.
            '--auto-compaction-mode', 'periodic',
            '--auto-compaction-retention', '1h',
            '--quota-backend-bytes', str(8 * 1024 * 1024 * 1024),
            # 1s: loki's kvstore rings trip default 5s as ENHANCE_YOUR_CALM.
            '--grpc-keepalive-min-time', '1s',
            # 10× defaults: USB-SATA wal_fsync ~2s, would trip elections.
            '--heartbeat-interval', '1000',
            '--election-timeout', '10000',
            # 2s lines up with worst-case fsync on this hardware.
            '--warning-apply-duration', '2s',
        ]

        exec_into(*args)


class EtcdEphemeral:
    # tmpfs etcd; bin/etcd/wrap tars data_dir to MinIO across restarts.
    # Genesis: wrapper no-ops until admin seeds the first backup.
    def __init__(self, peers, port_peer, port_client, hostname, etcid,
                 peer_addr, client_addr, user_name, cluster_state, data_dir,
                 backup_uri, timeout_sec, jitter_sec, s3_endpoint,
                 s3_user_key, s3_pass_key):
        self.peers = peers
        self.port_peer = port_peer
        self.port_client = port_client
        self.hostname = hostname
        self.etcid = etcid
        self.peer_addr = peer_addr
        self.client_addr = client_addr
        self.user_name = user_name
        self.cluster_state = cluster_state
        self.data_dir = data_dir
        self.backup_uri = backup_uri
        self.timeout_sec = timeout_sec
        self.jitter_sec = jitter_sec
        self.s3_endpoint = s3_endpoint
        self.s3_user_key = s3_user_key
        self.s3_pass_key = s3_pass_key

    def name(self):
        return self.user_name

    def user(self):
        return self.user_name

    def pkgs(self):
        yield {'pkg': 'bin/etcd/wrap'}

    def it_all(self):
        for x in self.peers:
            yield f'{x["hostname"]}=http://{x["ip"]}:{self.port_peer}'

    def prom_jobs(self):
        yield {
            'job_name': self.name(),
            'static_configs': [{'targets': [f'{self.client_addr}:{self.port_client}']}],
        }

    def run(self):
        os.makedirs(self.data_dir, exist_ok=True)

        if 'ETCDCTL_ENDPOINTS' in os.environ:
            os.environ.pop('ETCDCTL_ENDPOINTS')

        aws_key = get_key(self.s3_user_key).decode().strip()
        aws_secret = get_key(self.s3_pass_key).decode().strip()
        scheme, host = self.s3_endpoint.split('://', 1)
        mc_host = f'{scheme}://{aws_key}:{aws_secret}@{host}'

        etcd_argv = [
            '--name', self.hostname,
            '--data-dir', self.data_dir,
            '--initial-advertise-peer-urls',
            f'http://{self.peer_addr}:{self.port_peer}',
            '--listen-peer-urls',
            f'http://{self.peer_addr}:{self.port_peer}',
            '--listen-client-urls',
            f'http://{self.client_addr}:{self.port_client}',
            '--advertise-client-urls',
            f'http://{self.client_addr}:{self.port_client}',
            '--initial-cluster-token', self.etcid,
            '--initial-cluster', ','.join(self.it_all()),
            '--initial-cluster-state', self.cluster_state,
            '--auto-compaction-mode', 'periodic',
            '--auto-compaction-retention', '1h',
            '--quota-backend-bytes', str(8 * 1024 * 1024 * 1024),
            '--grpc-keepalive-min-time', '1s',
            '--heartbeat-interval', '1000',
            '--election-timeout', '10000',
            '--warning-apply-duration', '2s',
        ]

        wrap_argv = [
            'etcd_wrap',
            '--data-dir', self.data_dir,
            '--backup-uri', self.backup_uri,
            '--timeout', str(self.timeout_sec),
            '--jitter', str(self.jitter_sec),
            '--', 'etcd',
        ]

        # No user=: runpy is already etcd_3; su-exec would trip CAP_SETGID.
        exec_into(*wrap_argv, *etcd_argv,
                  PATH='/bin',
                  HOME=os.getcwd(),
                  TMPDIR=os.getcwd(),
                  MC_HOST_minio=mc_host)


class Federator:
    # Per-host aggregator: scrapes /federate from every Collector.
    def __init__(self, port, collector_port, hosts):
        self.port = port
        self.collector_port = collector_port
        self.hosts = list(hosts)

    def name(self):
        return 'federator'

    def pkgs(self):
        yield {
            'pkg': 'bin/prometheus',
        }

    def prom_port(self):
        return self.port

    def prepare(self):
        u = self.name()
        make_dirs(f'/home/{u}', owner=u)

    def config(self):
        return {
            'global': {
                'scrape_interval': '15s',
                'evaluation_interval': '15s',
            },
            'scrape_configs': [
                {
                    'job_name': 'federate',
                    'honor_labels': True,
                    # Drop source ts; else cluster-shaped metrics collide.
                    'honor_timestamps': False,
                    'metrics_path': '/federate',
                    'params': {'match[]': ['{job=~".+"}']},
                    'static_configs': [
                        {
                            'targets': [f'{h}.gofra:{self.collector_port}' for h in self.hosts],
                        },
                    ],
                },
            ],
        }

    def run(self):
        with memfd('prometheus.conf') as fn:
            with open(fn, 'w') as f:
                f.write(json.dumps(self.config(), sort_keys=True, indent=4))

            args = [
                'prometheus',
                f'--config.file={fn}',
                f'--storage.tsdb.path=/home/{self.name()}/',
                # 0.0.0.0: prometheus multi-listen broken (see Collector).
                f'--web.listen-address=0.0.0.0:{self.port}',
            ]

            exec_into(*args)


# Not a secret; non-default value skips first-login change form.
GRAFANA_ADMIN_PASSWORD = 'grafana'


class Grafana:
    def __init__(self, port, collector_port, loki_port, services):
        self.port = port
        self.collector_port = collector_port
        self.loki_port = loki_port
        self.services = services

    def name(self):
        return 'grafana'

    def state_dir(self):
        return f'/var/run/{self.name()}'

    def prom_port(self):
        # /metrics on main HTTP port; default ini has [metrics], no auth.
        return self.port

    def pkgs(self):
        yield {
            'pkg': 'bin/grafana',
        }

        yield {
            'pkg': 'aux/grafana',
            'prom_url': f'http://127.0.0.1:{self.collector_port}',
            'loki_url': f'http://127.0.0.1:{self.loki_port}',
            # b64+newlines: commas would collide with ix's k=v,k2=v2 syntax.
            'services_b64': base64.b64encode('\n'.join(self.services).encode()).decode(),
        }

        yield {
            'pkg': 'aux/grafana/gen',
        }

        yield {
            'pkg': 'bin/sched/grafana/reload',
            'delay': '10',
            'port': str(self.port),
            'password': GRAFANA_ADMIN_PASSWORD,
        }

    def ini(self):
        s = self.state_dir()

        return (
            '[server]\n'
            # 0.0.0.0: nebula-only bind broke local scrape (see Federator).
            'http_addr = 0.0.0.0\n'
            f'http_port = {self.port}\n'
            '[paths]\n'
            f'data = {s}/data\n'
            f'logs = {s}/logs\n'
            f'plugins = {s}/plugins\n'
            'provisioning = /ix/realm/system/share/grafana-provisioning\n'
            '[analytics]\n'
            'reporting_enabled = false\n'
            'check_for_updates = false\n'
            '[security]\n'
            'disable_gravatar = true\n'
            f'admin_password = {GRAFANA_ADMIN_PASSWORD}\n'
            # Disable grafana 13 k8s datasource; provisioning crash-loops.
            '[feature_toggles]\n'
            'kubernetesDatasources = false\n'
            'kubernetesDashboards = false\n'
            'kubernetesFolders = false\n'
        )

    def run(self):
        # Wipe state every boot; config is fully provisioning-managed.
        s = self.state_dir()
        shutil.rmtree(f'{s}/data', ignore_errors=True)
        os.makedirs(f'{s}/data', exist_ok=True)

        # Resolve a leaf to bypass grafana's plugin-loader symlink-escape check.
        sample = os.path.realpath('/ix/realm/system/share/grafana/conf/sample.ini')
        homepath = os.path.dirname(os.path.dirname(sample))

        with memfd('grafana.ini') as fn:
            with open(fn, 'w') as f:
                f.write(self.ini())

            exec_into(
                'grafana', 'server', '--config', fn, '--homepath', homepath,
                # Env var override; ini admin_password didn't stick on fresh DB.
                GF_SECURITY_ADMIN_PASSWORD=GRAFANA_ADMIN_PASSWORD,
            )


class Samogon:
    # SFTP over MinIO CAS. Read-only; fetches via `gorn ignite samogon`.
    def __init__(self, port, s3_endpoint):
        self.port = port
        self.s3_endpoint = s3_endpoint

    def name(self):
        return 'samogon'

    def users(self):
        # users[0]=root so run() reads /etc/keys before su-exec drops privs.
        return ['root', 'samogon']

    def home_dir(self):
        return f'/var/run/{self.name()}/std/home'

    def pkgs(self):
        yield {
            'pkg': 'bin/samogon',
        }

        yield {
            'pkg': 'etc/lab/user/home',
            'user': 'samogon',
            'user_home': self.home_dir(),
        }

    def prepare(self):
        make_dirs(self.home_dir(), owner='samogon')

    def run(self):
        # memfd inherits across su-exec so non-root reads host key.
        with memfd('host_key') as hk:
            with open(hk, 'w') as f:
                f.write(open('/etc/keys/ssh_ed25519').read())

            # storage.go mkdtemp's in cwd; default runsrv cwd is root-owned.
            os.chdir(self.home_dir())

            args = [
                'samogon', 'serve',
                '--listen', f'0.0.0.0:{self.port}',
                '--user', 'tv',
                '--pass', 'tv',
                '--host-key', hk,
            ]

            env = {
                'PATH': '/bin',
                'HOME': self.home_dir(),
                'AWS_ACCESS_KEY_ID': get_key('/s3/iam/samogon/key').decode().strip(),
                'AWS_SECRET_ACCESS_KEY': get_key('/s3/iam/samogon/secret').decode().strip(),
                'S3_ENDPOINT': self.s3_endpoint,
                'S3_BUCKET': 'samogon',
                'SAMOGON_S3_ROOT': 'torrents',
            }

            exec_into(*args, user='samogon', **env)


class SamogonBot:
    # Telegram bot for `samogon fetch`; cluster singleton via etcdctl lock.
    def __init__(self, s3_endpoint, gorn_api, tg_allow_users, etcd_endpoints):
        self.s3_endpoint = s3_endpoint
        self.gorn_api = gorn_api
        self.tg_allow_users = tg_allow_users
        self.etcd_endpoints = list(etcd_endpoints)

    def name(self):
        return 'samogon_bot'

    def user(self):
        return 'samogon_bot'

    def pkgs(self):
        yield {'pkg': 'bin/samogon'}
        # Params as dict keys, not in 'pkg'; to_srv() appends its own (...).
        yield {'pkg': 'bin/mc/gc/cron', 'root': '/gorn/samogon', 'hours': 1}

    def run(self):
        env = {
            'PATH': '/bin',
            'HOME': os.getcwd(),
            'TMPDIR': os.getcwd(),
            'TG_BOT_TOKEN': get_key('/samogon/bot/token').decode().strip(),
            'TG_ALLOW_USERS': self.tg_allow_users,
            'GORN_API': self.gorn_api,
            'ETCDCTL_ENDPOINTS': ','.join(self.etcd_endpoints),
            'AWS_ACCESS_KEY_ID': get_key('/s3/iam/samogon/key').decode().strip(),
            'AWS_SECRET_ACCESS_KEY': get_key('/s3/iam/samogon/secret').decode().strip(),
            'S3_ENDPOINT': self.s3_endpoint,
            'S3_BUCKET': 'samogon',
            'SAMOGON_S3_ROOT': 'torrents',
            # No direct outbound to telegram; route via local SOCKS5 exit.
            'SAMOGON_SOCKS5': '127.0.0.1:8015',
        }

        # Stagger lock attempts so all 3 hosts don't dogpile etcd.
        time.sleep(random.random() * 10)

        exec_into('etcdctl', 'lock', '/lock/samogon_bot', 'samogon', 'bot', **env)


class JobScheduler:
    # Cluster cron; singleton via etcdctl lock /lock/job/scheduler.
    def __init__(self, gorn_api, s3_endpoint, etcd_endpoints, etcd_persist_endpoints):
        self.gorn_api = gorn_api
        self.s3_endpoint = s3_endpoint
        # etcd_endpoints: tmpfs etcd_3; etcd_persist_endpoints: cold-safe.
        self.etcd_endpoints = list(etcd_endpoints)
        self.etcd_persist_endpoints = list(etcd_persist_endpoints)

    def name(self):
        return 'job_scheduler'

    def user(self):
        return 'job_scheduler'

    def py_modules(self):
        # Cluster-wide pip deps shared by scheduler cron scripts.
        return [
            'pip/tqdm',
            'pip/PyYAML',
            'pip/requests',
            'pip/filelock',
        ]

    def pkgs(self):
        yield {'pkg': 'bin/job/scheduler'}

    def run(self):
        aws_key = get_key('/s3/user').decode().strip()
        aws_secret = get_key('/s3/password').decode().strip()
        # Pre-baked MC_HOST_minio so cron files forward without re-deriving.
        mc_host = self.s3_endpoint.replace('://', f'://{aws_key}:{aws_secret}@', 1)

        env = {
            'PATH': '/bin',
            'HOME': os.getcwd(),
            'TMPDIR': os.getcwd(),
            'GORN_API': self.gorn_api,
            'S3_ENDPOINT': self.s3_endpoint,
            'ETCDCTL_ENDPOINTS': ','.join(self.etcd_endpoints),
            'ETCDCTL_ENDPOINTS_PERSIST': ','.join(self.etcd_persist_endpoints),
            'AWS_ACCESS_KEY_ID': aws_key,
            'AWS_SECRET_ACCESS_KEY': aws_secret,
            'MC_HOST_minio': mc_host,
            # HF/GHCR sync tokens; cron files $-expand.
            'HF_TOKEN': get_key('/hf/token').decode().strip(),
            'GHCR_TOKEN': get_key('/ghcr/token').decode().strip(),
        }

        # Stagger lock attempts across hosts.
        time.sleep(random.random() * 10)

        exec_into('etcdctl', 'lock', '/lock/job/scheduler', 'job_scheduler', **env)


class Loki:
    # HA per-host. Ring on etcd_2 (gossip per grafana/loki#14019).
    def __init__(self, port, s3_endpoint, peers, me, etcd_endpoints):
        self.v = 1
        self.port = port
        self.s3_endpoint = s3_endpoint
        self.peers = list(peers)
        self.me = me
        self.etcd_endpoints = list(etcd_endpoints)

    def name(self):
        return 'loki'

    def users(self):
        return ['root', 'loki']

    def home_dir(self):
        return f'/var/run/{self.name()}/std/home'

    def pkgs(self):
        yield {
            'pkg': 'bin/loki',
        }

        yield {
            'pkg': 'etc/lab/user/home',
            'user': 'loki',
            'user_home': self.home_dir(),
        }

    def prepare(self):
        # Wipe state every boot; ring is authoritative in etcd.
        shutil.rmtree(self.home_dir(), ignore_errors=True)
        make_dirs(self.home_dir(), owner='loki')

    def prom_port(self):
        return self.port

    def config(self):
        scheme, rest = self.s3_endpoint.split('://', 1)

        return {
            'auth_enabled': False,
            'server': {
                'http_listen_port': self.port,
                'grpc_listen_port': 9095,
                'log_level': 'info',
            },
            'common': {
                'path_prefix': self.home_dir(),
                'storage': {
                    's3': {
                        'endpoint': rest,
                        'bucketnames': 'loki',
                        'access_key_id': get_key('/s3/iam/loki/key').decode().strip(),
                        'secret_access_key': get_key('/s3/iam/loki/secret').decode().strip(),
                        's3forcepathstyle': True,
                        'insecure': scheme == 'http',
                    },
                },
                'replication_factor': min(3, max(1, len(self.peers))),
                'ring': {
                    'instance_addr': f'{self.me}.gofra',
                    'kvstore': {
                        'store': 'etcd',
                        'etcd': {
                            'endpoints': self.etcd_endpoints,
                            'dial_timeout': '5s',
                        },
                    },
                },
            },
            'schema_config': {
                'configs': [
                    {
                        'from': '2026-01-01',
                        'store': 'tsdb',
                        'object_store': 's3',
                        'schema': 'v13',
                        'index': {'prefix': 'index_', 'period': '24h'},
                    },
                ],
            },
            'limits_config': {
                'allow_structured_metadata': True,
            },
            'distributor': {
                'rate_store': {
                    # 2s absorbs nebula jitter; default 500ms times out.
                    'ingester_request_timeout': '2s',
                },
            },
        }

    def run(self):
        with memfd('loki.yaml') as fn:
            with open(fn, 'w') as f:
                f.write(json.dumps(self.config(), indent=2, sort_keys=True))

            exec_into(
                'loki', '-config.file', fn,
                user='loki',
                PATH='/bin',
                HOME=self.home_dir(),
            )


class Promtail:
    # Per-host log shipper to local Loki. sources set in do()'s 2nd pass.
    def __init__(self, port, loki_port, me):
        self.port = port
        self.loki_port = loki_port
        self.me = me
        self.sources = []

    def name(self):
        return 'promtail'

    def user(self):
        return 'root'

    def users(self):
        return ['root']

    def pkgs(self):
        yield {
            'pkg': 'bin/promtail',
        }

    def prom_port(self):
        return self.port

    def config(self):
        scrape_configs = []

        for s in self.sources:
            labels = {**s.get('labels', {})}
            labels['host'] = self.me
            labels['__path__'] = s['path']

            sc = {
                'job_name': s['job_name'],
                'static_configs': [{'targets': ['localhost'], 'labels': labels}],
            }

            if 'pipeline_stages' in s:
                sc['pipeline_stages'] = s['pipeline_stages']

            scrape_configs.append(sc)

        return {
            'server': {
                'http_listen_port': self.port,
                'grpc_listen_port': 9096,
            },
            'positions': {
                'filename': f'/var/run/{self.name()}/std/positions.yaml',
            },
            'clients': [
                {'url': f'http://localhost:{self.loki_port}/loki/api/v1/push'},
            ],
            'scrape_configs': scrape_configs,
        }

    def run(self):
        with memfd('promtail.yaml') as fn:
            with open(fn, 'w') as f:
                f.write(json.dumps(self.config(), indent=2, sort_keys=True))

            exec_into('promtail', '-config.file', fn, PATH='/bin')


class TailLog:
    # Loki-free fallback; per-host HTTP, last 50k lines in-process.
    IX_TINYLOGS = (
        'autologin_1',
        'autoupdate_ix',
        'chrony',
        'dbus',
        'dnsproxy',
        'irqbalance',
        'mdnsd',
        'mdnsd_dns',
        'mdnsd_exporter',
        'resolvconf',
        'sched10',
        'sched100',
        'sched1000',
        'syslogd',
    )

    def __init__(self, port, me, me_nebula_ip):
        self.port = port
        self.me = me
        self.me_nebula_ip = me_nebula_ip
        self.paths = []

    def name(self):
        return 'tail_log'

    def user(self):
        return 'root'

    def pkgs(self):
        yield {'pkg': 'bin/tail/log'}

    def log_sources(self):
        for svc in self.IX_TINYLOGS:
            yield {
                'job_name': f'{svc}/tinylog',
                'path': f'/var/run/{svc}/std/current',
                'labels': {'service': svc, 'stream': 'tinylog'},
            }

    def run(self):
        exec_into(
            'ix_tail_log',
            self.me_nebula_ip,
            str(self.port),
            *sorted(set(self.paths)),
        )


class OgorodServe:
    # HTTP git: refs in etcd_2 (CAS), packs in MinIO. See ogorod/CLAUDE.md.
    def __init__(self, port, s3_endpoint, etcd_endpoints, bind_addr, suffix=None):
        self.port = port
        self.s3_endpoint = s3_endpoint
        self.etcd_endpoints = list(etcd_endpoints)
        self.bind_addr = bind_addr
        self.suffix = suffix

    def name(self):
        if self.suffix:
            return f'ogorod_serve_{self.suffix}'

        return 'ogorod_serve'

    def users(self):
        # users[0]=root: prepare() chowns cache dir before su-exec drop.
        return ['root', self.name()]

    def home_dir(self):
        return f'/var/run/{self.name()}/home'

    def cache_dir(self):
        return f'{self.home_dir()}/cache'

    def pkgs(self):
        yield {'pkg': 'bin/ogorod'}
        yield {'pkg': 'bin/git/unwrap'}

        yield {
            'pkg': 'etc/lab/user/home',
            'user': self.name(),
            'user_home': self.home_dir(),
        }

    def prepare(self):
        make_dirs(self.home_dir(), owner=self.name())
        make_dirs(self.cache_dir(), owner=self.name())

    def run(self):
        env = {
            'PATH': '/bin',
            'HOME': self.home_dir(),
            'OGOROD_ETCD_ENDPOINTS': ','.join(self.etcd_endpoints),
            'OGOROD_S3_ENDPOINT': self.s3_endpoint,
            'OGOROD_S3_ACCESS_KEY': get_key('/s3/iam/ogorod/key').decode().strip(),
            'OGOROD_S3_SECRET_KEY': get_key('/s3/iam/ogorod/secret').decode().strip(),
            'OGOROD_S3_BUCKET': 'ogorod',
        }

        exec_into(
            'ogorod', 'serve',
            '--listen', f'{self.bind_addr}:{self.port}',
            '--cache-dir', self.cache_dir(),
            user=self.name(),
            **env,
        )


class OgorodThin:
    # Sibling of OgorodServe; cluster-sync moved into per-binary wrappers. A/B.
    def __init__(self, port, s3_endpoint, etcd_endpoints, bind_addr, suffix=None):
        self.port = port
        self.s3_endpoint = s3_endpoint
        self.etcd_endpoints = list(etcd_endpoints)
        self.bind_addr = bind_addr
        self.suffix = suffix

    def name(self):
        if self.suffix:
            return f'ogorod_thin_{self.suffix}'

        return 'ogorod_thin'

    def users(self):
        return ['root', self.name()]

    def home_dir(self):
        return f'/var/run/{self.name()}/home'

    def cache_dir(self):
        return f'{self.home_dir()}/cache'

    def bin_dir(self):
        return f'{self.home_dir()}/bin'

    def pkgs(self):
        yield {'pkg': 'bin/ogorod'}
        yield {'pkg': 'bin/git/unwrap'}

        yield {
            'pkg': 'etc/lab/user/home',
            'user': self.name(),
            'user_home': self.home_dir(),
        }

    def prepare(self):
        make_dirs(self.home_dir(), owner=self.name())
        make_dirs(self.cache_dir(), owner=self.name())
        make_dirs(self.bin_dir(), owner=self.name())

    def run(self):
        env = {
            'PATH': '/bin',
            'HOME': self.home_dir(),
            'OGOROD_ETCD_ENDPOINTS': ','.join(self.etcd_endpoints),
            'OGOROD_S3_ENDPOINT': self.s3_endpoint,
            'OGOROD_S3_ACCESS_KEY': get_key('/s3/iam/ogorod/key').decode().strip(),
            'OGOROD_S3_SECRET_KEY': get_key('/s3/iam/ogorod/secret').decode().strip(),
            'OGOROD_S3_BUCKET': 'ogorod',
        }

        exec_into(
            'ogorod', 'serve-thin',
            '--listen', f'{self.bind_addr}:{self.port}',
            '--cache-dir', self.cache_dir(),
            '--bin-dir', self.bin_dir(),
            user=self.name(),
            **env,
        )


class Secrets:
    def __init__(self, port, etcd_endpoints):
        self.port = port
        self.etcd_endpoints = list(etcd_endpoints)

    def name(self):
        return 'secrets'

    def pkgs(self):
        yield {
            'pkg': 'bin/secrets',
        }

    def run(self):
        tout = int(random.random() * 1000 + 500)

        args = [
            'timeout',
            str(tout) + 's',
            'ix_serve_secrets',
            self.port,
        ]

        exec_into(*args, ETCDCTL_ENDPOINTS=','.join(self.etcd_endpoints))


class SecretsV2:
    # Git-shipped encrypted store; passphrase from /master.key in EFI vars.
    def __init__(self, port):
        self.port = port

    def name(self):
        return 'secrets_v2'

    def users(self):
        # users[0]=root: persdb needs CAP_SYS_ADMIN to read EFI vars.
        return ['root', 'secrets_v2']

    def pkgs(self):
        yield {'pkg': 'bin/secrets/v2'}

    def run(self):
        # Fetch passphrase as root, pass via env; server then runs unprivileged.
        pp = subprocess.check_output(['persdb', 'get', '/master.key']).decode('utf-8').strip()

        exec_into(
            'ix_serve_secrets_v2',
            str(self.port),
            '/ix/realm/system/share/secrets-v2/store',
            user='secrets_v2',
            SECRETS_V2_MASTER_KEY=pp,
        )


class CO2Mon:
    def __init__(self, port):
        self.port = port

    def name(self):
        return 'co2_mon'

    def user(self):
        return 'root'

    def pkgs(self):
        yield {
            'pkg': 'bin/co2mon',
        }

    def run(self):
        exec_into('co2mond')


class ClusterMap:
    def __init__(self, conf):
        self.conf = conf

    def it_cluster(self):
        p = self.conf['ports']

        neb_map = {}
        bal_map = []
        all_etc_1 = []
        all_etc_2 = []
        all_etc_3 = []

        # gofra peer table: VIP → underlay IPs. 103/24 prod, 104/24 staging.
        gofra_hosts = {}
        gofra2_hosts = {}

        for hn in ['lab1', 'lab2', 'lab3']:
            h = self.conf['by_host'][hn]
            n = int(hn[-1])
            underlay = [net['ip'] for net in h['net']]
            gofra_hosts[f'192.168.103.{15 + n}'] = underlay
            gofra2_hosts[f'192.168.104.{15 + n}'] = underlay

        for hn in ['lab1', 'lab2', 'lab3']:
            h = self.conf['by_host'][hn]

            all_etc_1.append({
                'hostname': hn,
                'ip': h['gofra']['ip'],
            })

            all_etc_2.append({
                'hostname': hn,
                'ip': h['gofra']['ip'],
            })

            all_etc_3.append({
                'hostname': hn,
                'ip': h['gofra']['ip'],
            })

            # Primary etcd: secrets, ogorod refs, version keys, gorn election.
            yield {
                'host': hn,
                'serv': EtcdPrivate(
                    all_etc_1,
                    p['etcd_1_peer'],
                    p['etcd_1_client'],
                    hn,
                    'etcd_1',
                    h['gofra']['ip'],
                    '127.0.0.1',
                    'etcd_1',
                    'new',
                ),
            }

            # Secondary etcd: loki's ring kvstore + future coordination tenants.
            yield {
                'host': hn,
                'serv': EtcdPrivate(
                    all_etc_2,
                    p['etcd_2_peer'],
                    p['etcd_2_client'],
                    hn,
                    'etcd_2',
                    h['gofra']['ip'],
                    '127.0.0.1',
                    'etcd_2',
                    'new',
                ),
            }

            # Tertiary etcd: tmpfs, gorn queue+cron locks; id via S3 tar.zstd.
            yield {
                'host': hn,
                'serv': EtcdEphemeral(
                    all_etc_3,
                    p['etcd_3_peer'],
                    p['etcd_3_client'],
                    hn,
                    'etcd_3',
                    h['gofra']['ip'],
                    '127.0.0.1',
                    'etcd_3',
                    'existing',
                    data_dir='/var/run/etcd_3/data',
                    backup_uri=f'minio/etcd/3/{hn}.tar.zstd',
                    timeout_sec=12 * 3600,
                    jitter_sec=6 * 3600,
                    s3_endpoint=f"http://127.0.0.1:{p['minio']}",
                    s3_user_key='/s3/iam/etcd/key',
                    s3_pass_key='/s3/iam/etcd/secret',
                ),
            }

        for hn in ['lab1', 'lab2', 'lab3']:
            h = self.conf['by_host'][hn]
            nb = h['nebula']
            mio_cmap = 'http://lab{1...3}.gofra:' + str(p['minio']) + '/var/mnt/minio/{1...3}/data'

            minio = MinIO(h['gofra']['ip'], p['minio'], mio_cmap)

            yield {
                'host': hn,
                'serv': minio,
            }

            mc_host = nb['ip']
            mc_port = p['minio_web']
            mc_serv = 'http://' + minio.addr

            yield {
                'host': hn,
                'serv': MinioConsole(mc_host, mc_port, mc_serv),
            }

        for h in self.conf['hosts']:
            hn = h['hostname']

            if False:
                for i in range(0, 16):
                    yield {
                        'host': hn,
                        'serv': Heat(i + 1),
                    }

            yield {
                'host': hn,
                'serv': DropBear2(p['sshd_rec']),
            }

            yield {
                'host': hn,
                'serv': SftpD(p['sftp_d'], 'geesefs'),
            }

            yield {
                'host': hn,
                'serv': Collector(p['collector'], hn),
            }

            yield {
                'host': hn,
                'serv': Federator(p['federator'], p['collector'], [x['hostname'] for x in self.conf['hosts']]),
            }

            yield {
                'host': hn,
                'serv': Grafana(p['grafana'], p['federator'], p['loki'], self.conf['services']),
            }

            yield {
                'host': hn,
                'serv': Loki(
                    port=p['loki'],
                    s3_endpoint=f"http://127.0.0.1:{p['minio']}",
                    peers=[x['hostname'] for x in self.conf['hosts']],
                    me=hn,
                    etcd_endpoints=[f"127.0.0.1:{p['etcd_2_client']}"],
                ),
            }

            yield {
                'host': hn,
                'serv': Promtail(
                    port=p['promtail'],
                    loki_port=p['loki'],
                    me=hn,
                ),
            }

            yield {
                'host': hn,
                'serv': TailLog(
                    port=p['tail_log'],
                    me=hn,
                    me_nebula_ip=h['nebula']['ip'],
                ),
            }

            ogorod_etcd = [f"127.0.0.1:{p['etcd_2_client']}"]
            ogorod_s3 = f"http://127.0.0.1:{p['minio']}"

            for bind, suffix in [(h['gofra']['ip'], None), ('127.0.0.1', 'local')]:
                yield {
                    'host': hn,
                    'serv': OgorodServe(
                        port=p['ogorod_serve'],
                        s3_endpoint=ogorod_s3,
                        etcd_endpoints=ogorod_etcd,
                        bind_addr=bind,
                        suffix=suffix,
                    ),
                }

                yield {
                    'host': hn,
                    'serv': OgorodThin(
                        port=p['ogorod_thin'],
                        s3_endpoint=ogorod_s3,
                        etcd_endpoints=ogorod_etcd,
                        bind_addr=bind,
                        suffix=suffix,
                    ),
                }

            yield {
                'host': hn,
                'serv': CO2Mon(p['co2_mon']),
            }

            yield {
                'host': hn,
                'serv': Secrets(p['secrets'], etcd_endpoints=[f"127.0.0.1:{p['etcd_1_client']}"]),
            }

            yield {
                'host': hn,
                'serv': Samogon(
                    p['samogon'],
                    s3_endpoint=f"http://127.0.0.1:{p['minio']}",
                ),
            }

            yield {
                'host': hn,
                'serv': SamogonBot(
                    s3_endpoint=f"http://127.0.0.1:{p['minio']}",
                    gorn_api=f"http://127.0.0.1:{p['gorn_ctl']}",
                    tg_allow_users=TG_ALLOW_USERS,
                    etcd_endpoints=[f"127.0.0.1:{p['etcd_1_client']}"],
                ),
            }

            yield {
                'host': hn,
                'serv': JobScheduler(
                    gorn_api=f"http://127.0.0.1:{p['gorn_ctl']}",
                    s3_endpoint=f"http://127.0.0.1:{p['minio']}",
                    etcd_endpoints=[f"127.0.0.1:{p['etcd_3_client']}"],
                    etcd_persist_endpoints=[f"127.0.0.1:{p['etcd_1_client']}"],
                ),
            }

            yield {
                'host': hn,
                'serv': SecretsV2(p['secrets_v2']),
            }

            yield {
                'host': hn,
                'serv': BalancerHttp(p['proxy_http'], p['proxy_http_mgmt'], bal_map),
            }

            yield {
                'host': hn,
                'serv': SecondIP('10.0.0.32/24', etcd_endpoints=[f"127.0.0.1:{p['etcd_1_client']}"]),
            }

            yield {
                'host': hn,
                'serv': SecondIP('10.0.0.33/24', etcd_endpoints=[f"127.0.0.1:{p['etcd_1_client']}"]),
            }

            nb = h['nebula']

            yield {
                'host': hn,
                'serv': DropBear(nb['ip'], p['sshd']),
            }

            all_s5s = []

            for tun in SSH_TUNNELS:
                k = tun['key']

                yield {
                    'host': hn,
                    'serv': SshTunnel(
                        '127.0.0.1:' + str(p[k]),
                        tun['addr'],
                        tun['keyn'],
                        k,
                        tun['port'],
                        tun['tout'],
                    ),
                }

                all_s5s.append('127.0.0.1:' + str(p[k]))

            yield {
                'host': hn,
                'serv': SocksProxy(p['socks_proxy'], all_s5s),
            }

            yield {
                'host': hn,
                'serv': IPerf(p['i_perf']),
            }

            yield {
                'host': hn,
                'serv': IPerf3(p['i_perf_3']),
            }

            yield {
                'host': hn,
                'serv': NodeExporter(p['node_exporter']),
            }

            nn_port = p['nebula_node']
            nn_adv = [x['ip'] + f':{nn_port}' for x in h['net']]
            # smap pinned to gofra overlay so peer traffic stripes via TUN.
            neb_map[nb['ip']] = [h['gofra']['ip'] + f':{nn_port}']

            yield {
                'host': hn,
                'serv': NebulaNode(hn, nn_port, neb_map, p['nebula_node_prom'], nn_adv, nb['ip']),
            }

            yield {
                'host': hn,
                'serv': Gofra(hn, p['gofra'], gofra_hosts, h['gofra']['ip'] + '/24'),
            }

            yield {
                'host': hn,
                'serv': Gofra2(hn, p['gofra2'], gofra2_hosts, f'192.168.104.{15 + int(hn[-1])}/24'),
            }

            if lh := h.get('nebula', {}).get('lh', None):
                lh_port = p['nebula_lh']
                pm = (h['ip'], lh_port, int(lh['port']))
                neb_reals = list(it_nebula_reals(lh, h, lh_port))
                neb_map[lh['vip']] = list(f'{h}:{p}' for h, p in neb_reals)

                yield {
                    'host': hn,
                    'serv': NebulaLh(lh['name'], lh_port, neb_map, p['nebula_lh_prom'], pm),
                }

        gorn_endpoints = []

        for hn, n in GORN_N.items():
            h = self.conf['by_host'][hn]
            nb = h['nebula']
            gofra_ip = h['gofra']['ip']

            for i in range(n):
                port = p[f'gorn_{i}']
                user = f'gorn_{i}'

                yield {
                    'host': hn,
                    'serv': GornSsh(i, gofra_ip, port, nb['hostname']),
                }

                gorn_endpoints.append({
                    'host': gofra_ip,
                    'port': port,
                    'user': user,
                    # work/ is per-task scratch; gorn wrap mounts tmpfs on top.
                    'path': f'/var/run/{user}/work',
                    'log_path': f'/var/run/{user}/home/gorn-wrap.log',
                    'nebula_host': nb['hostname'],
                })

        # gorn → etcd_3 (tmpfs); avoids etcd_1 slow-fsync killing keepalive.
        gorn_etcd = [f"127.0.0.1:{p['etcd_3_client']}"]

        for hn in GORN_N:
            h = self.conf['by_host'][hn]

            s3 = {
                'endpoint': f"http://127.0.0.1:{p['minio']}",
                'region': 'minio',
                'bucket': 'gorn',
                'use_path_style': True,
            }

            yield {
                'host': hn,
                'serv': Gorn(gorn_endpoints, s3, gorn_etcd),
            }

            yield {
                'host': hn,
                'serv': GornCtl(gorn_endpoints, s3, f"127.0.0.1:{p['gorn_ctl']}", gorn_etcd),
            }

            yield {
                'host': hn,
                'serv': GornCtlNebula(gorn_endpoints, s3, f"{h['nebula']['ip']}:{p['gorn_ctl_nb']}", gorn_etcd),
            }

            yield {
                'host': hn,
                'serv': GornWeb(f"http://127.0.0.1:{p['gorn_ctl']}", f"{h['nebula']['ip']}:{p['gorn_web']}"),
            }

            yield {
                'host': hn,
                'serv': GornProm(gorn_endpoints, s3, p['gorn_prom'], gorn_etcd),
            }

            yield {
                'host': hn,
                'serv': MolotWeb(f"{h['nebula']['ip']}:{p['molot_web']}", f"http://127.0.0.1:{p['gorn_ctl']}", f"http://127.0.0.1:{p['minio']}", 'molot'),
            }


def exec_into(*args, user=None, **kwargs):
    args = [str(x) for x in args]

    if user:
        args = ['su-exec', user] + args

    env = os.environ.copy()

    for k, v in kwargs.items():
        env[str(k)] = str(v)

    os.execvpe(args[0], args, env)


def gen_runner(srv):
    ctx = base64.b64encode(pickle.dumps({'srv': srv, 'hash': class_src_hash(type(srv))})).decode()
    scr = 'exec runpy ' + ctx + ' ${@}'

    return base64.b64encode(scr.encode()).decode()


_CLASS_SRC_TEXT = {}


def class_src_hash(cls):
    # ast.dump ignores whitespace/comments; cosmetic edits don't churn.
    parts = []

    for c in cls.__mro__:
        if c is object:
            continue

        parts.append(ast.dump(ast.parse(_CLASS_SRC_TEXT[c.__name__])))

    return hashlib.sha256('\n'.join(parts).encode()).hexdigest()[:16]


def it_norm(n):
    for c in n:
        if c == c.upper():
            yield '_'
            yield c.lower()
        else:
            yield c


def norm(n):
    res = ''.join(it_norm(n))

    while res and res[0] == '_':
        res = res[1:]

    return res


class Service:
    def __init__(self, srv):
        self.srv = srv

    def iter_py_modules(self):
        try:
            return self.srv.py_modules()
        except AttributeError:
            return []

    def iter_upnp(self):
        try:
            return self.srv.iter_upnp()
        except AttributeError:
            return []

    def home_dir(self):
        try:
            return self.srv.home_dir()
        except AttributeError:
            return f'/home/{self.user()}'

    def l7_balancer(self):
        try:
            yield from self.srv.l7_balancer()
        except AttributeError:
            pass

    def prom_ports(self):
        try:
            yield self.srv.prom_port()
        except AttributeError:
            pass

        try:
            yield from self.srv.prom_ports()
        except AttributeError:
            pass

    def prom_jobs(self):
        try:
            yield from self.srv.prom_jobs()
        except AttributeError:
            pass

        ports = list(self.prom_ports())

        if ports:
            yield {
                'job_name': self.name(),
                'static_configs': [
                    {
                        'targets': [f'localhost:{p}' for p in ports],
                    },
                ],
            }

    def iter_log_sources(self):
        # Default tinylog source + any srv.log_sources() extras.
        name = self.name()

        yield {
            'job_name': f'{name}/tinylog',
            'path': f'/var/run/{name}/std/current',
            'labels': {'service': name, 'stream': 'tinylog'},
        }

        try:
            extras = self.srv.log_sources()
        except AttributeError:
            return

        for s in extras:
            lbl = dict(s.get('labels', {}))
            lbl.setdefault('service', name)
            lbl.setdefault('stream', 'custom')

            yield {**s, 'labels': lbl}

    def enabled(self):
        return not self.disabled()

    def disabled(self):
        try:
            self.srv.run
        except AttributeError:
            return True

        try:
            return self.srv.disabled()
        except AttributeError:
            pass

        return False

    def name(self):
        try:
            return self.srv.name()
        except AttributeError:
            return norm(self.srv.__class__.__name__)

    def user(self):
        try:
            return self.srv.user()
        except AttributeError:
            try:
                return self.srv.users()[0]
            except AttributeError:
                pass

        return self.name()

    def it_users(self):
        yield self.user()

        try:
            yield from self.srv.users()
        except AttributeError:
            pass

    def users(self):
        return list(sorted(frozenset(self.it_users())))

    def serialize(self):
        srv_pkgs = []

        try:
            srv_pkgs = list(self.srv.pkgs())
        except AttributeError:
            pass

        yield from srv_pkgs

        for user in self.users():
            yield {
                'pkg': 'etc/lab/user',
                'user': user,
            }

        # Disabled: empty xiaomi_passwd collapses argv, xapi.py crashes.
        if False:
            for rec in self.iter_upnp():
                yield {
                    'pkg': 'bin/xiaomi',
                    'upnp_ip': rec['addr'],
                    'upnp_port': rec['port'],
                    'upnp_ext_port': rec['ext_port'],
                    'upnp_proto': rec['proto'],
                    'xiaomi_gw': '10.0.0.1',
                    'xiaomi_passwd': '', # get_key('/xiaomi/passwd').decode().strip(),
                    'xiaomi_name': str(rec['ext_port']) + '_' + rec['proto'],
                    'xiaomi_proto': {'TCP': 1, 'UDP': 2}[rec['proto']],
                    'delay': 100,
                }

        # extra_deps bakes runtime pkg uids; bumps trigger pid1 restart.
        yield {
            'pkg': 'bin/run/sh',
            'srv_dir': self.name(),
            'runsh_script': gen_runner(self.srv),
            'srv_user': self.user(),
            'extra_deps': base64.b64encode('\n'.join(to_srv(**p) for p in srv_pkgs).encode()).decode(),
        }


def gen_host(n):
    ip = 64 + (n - 1) * 4

    def gen_net(j):
        return {
            'ip': f'10.0.0.{ip + j}',
            'gw': '10.0.0.1',
            'nm': 24,
            'if': f'eth{j}',
        }

    return {
        'disabled': ['dhcpcd'],
        'hostname': f'lab{n}',
        'nebula': {
            'hostname': f'lab{n}.nebula',
            'ip': '192.168.100.' + str(15 + n),
            'lh': {
                'name': f'lh{n}',
                'vip': f'192.168.100.{n}',
                'ip': '5.188.103.251',
                'port': '424' + str(n + 1),
            },
        },
        'net': [gen_net(j) for j in (0, 1, 2, 3)],
    }


def to_srv(pkg='', **args):
    if args:
        return pkg + '(' + ','.join(f'{x}={y}' for x, y in args.items()) + ')'

    return pkg


def it_pkgs(srvs, code):
    for s in srvs:
        yield from s.serialize()

    yield {
        'pkg': 'bin/mk/file',
        'file_path': 'bin/runpy',
        'file_data': base64.b64encode(code.encode()).decode(),
    }


def it_srvs(srvs, code, flags):
    for x in it_pkgs(srvs, code):
        args = {}

        args.update(flags)
        args.update(x)

        yield to_srv(**args)


def do(code):
    for node in ast.parse(code).body:
        if isinstance(node, ast.ClassDef):
            _CLASS_SRC_TEXT[node.name] = ast.get_source_segment(code, node)

    # Anchor classes to synthetic 'cg' so pickle whichmodule() resolves.
    cg_mod = sys.modules.setdefault('cg', types.ModuleType('cg'))

    for name, obj in list(globals().items()):
        if isinstance(obj, type) and obj.__module__ == 'builtins':
            obj.__module__ = 'cg'
            setattr(cg_mod, name, obj)

    hosts = [gen_host(h) for h in (1, 2, 3)]

    for x in hosts:
        x['ip'] = x['net'][0]['ip']
        n = int(x['hostname'][-1])
        x['gofra'] = {
            'hostname': f'{x["hostname"]}.gofra',
            'ip': f'192.168.103.{15 + n}',
        }

    ports = {
        'sshd': 22,
        'nebula_lh': 4242,
        'nebula_node': 4243,
        'torrent_webui': 8000,
        'ftpd': 8001,
        'sftp_d': 8002,
        'mirror_http': 8003,
        'mirror_rsyncd': 8004,
        'i_perf': 8006,
        'i_perf_3': 8049,
        'node_exporter': 8007,
        'collector': 8008,
        'nebula_node_prom': 8009,
        'nebula_lh_prom': 8010,
        'ssh_3': 8011,
        'minio': 8012,
        'minio_web': 8013,
        'socks_proxy': 8015,
        'ssh_cz_tunnel': 8017,
        'ssh_jopa_tunnel': 8018,
        'co2_mon': 8019,
        'proxy_http': 8080,
        'proxy_http_mgmt': 8081,
        'proxy_https': 8090,
        'etcd_1_client': 8020,
        'etcd_1_peer': 8021,
        'etcd_2_client': 8036,
        'etcd_2_peer': 8037,
        'etcd_3_client': 8042,
        'etcd_3_peer': 8043,
        'secrets': 8022,
        'sshd_rec': 8023,
        'secrets_v2': 8034,
        'grafana': 8029,
        'federator': 8030,
        'samogon': 8031,
        'loki': 8032,
        'promtail': 8033,
        'tail_log': 8040,
        'ogorod_serve': 8035,
        'ogorod_thin': 8038,
        'gofra': 8050,
        'gofra2': 8051,
    }

    users = {
        'collector': 1001,
        'node_exporter': 1003,
        'torrent': 1004,
        'sftp_d': 1005,
        'balancer_http': 1006,
        'git_lab': 1007,
        'git_ci': 1008,
        'h_z': 1009,
        'i_perf': 1011,
        'i_perf_3': 1029,
        'nebula_lh': 1012,
        'minio_1': 1013,
        'minio_2': 1014,
        'minio_3': 1015,
        'mirror': 1016,
        'minio': 1017,
        'minio_console': 1018,
        'pf': 1019,
        'socks_proxy': 1021,
        'ssh_cz_tunnel': 1023,
        'ssh_jopa_tunnel': 1024,
        'etcd_1': 2010,
        'etcd_2': 2003,
        'etcd_3': 2011,
        'samogon_bot': 2004,
        'job_scheduler': 2005,
        'secrets': 1027,
        'secrets_v2': 1028,
        'grafana': 1094,
        'federator': 2000,
        'samogon': 2001,
        'loki': 2002,
        'ogorod_serve': 2006,
        'ogorod_thin': 2007,
        'ogorod_serve_local': 2008,
        'ogorod_thin_local': 2009,
    }

    for i in range(0, 64):
        users['heat_' + str(i + 1)] = 1030 + i

    users['gorn'] = 1099
    users['gorn_ctl'] = 1098
    users['gorn_web'] = 1097
    users['gorn_ctl_nb'] = 1096
    users['gorn_prom'] = 1095
    users['molot_web'] = 1026
    users['gofra'] = 1094
    users['gofra2'] = 1010
    ports['gorn_ctl'] = 8025
    ports['gorn_web'] = 8026
    ports['gorn_ctl_nb'] = 8027
    ports['gorn_prom'] = 8028
    ports['molot_web'] = 8052

    gorn_max = max(GORN_N.values(), default=0)

    for i in range(gorn_max):
        ports[f'gorn_{i}'] = 9000 + i
        users[f'gorn_{i}'] = 1100 + i

    by_name = dict()

    for h in hosts:
        by_name[h['hostname']] = h

    # Shared list ref; Grafana's ctor stores it, populated below after walk.
    cluster_services = []

    cconf = {
        'hosts': hosts,
        'ports': ports,
        'users': users,
        'by_host': by_name,
        'services': cluster_services,
    }

    by_host = collections.defaultdict(list)
    by_addr = dict()

    py_modules = []
    hndl_by_host = []

    for rec in ClusterMap(cconf).it_cluster():
        hndl = Service(rec['serv'])

        py_modules.extend(hndl.iter_py_modules())

        host = rec['host']
        addr = host + ':' + hndl.name()

        by_host[host].append(hndl)
        by_addr[addr] = hndl
        hndl_by_host.append((host, hndl))

    # Populate Grafana's shared services list.
    cluster_services.extend(sorted({h.name() for _, h in hndl_by_host}))

    # Second pass: routing/registration needs by_addr fully populated.
    for host, hndl in hndl_by_host:
        for job in hndl.prom_jobs():
            by_addr[f'{host}:collector'].srv.jobs.append(job)

        promtail_key = f'{host}:promtail'

        if promtail_key in by_addr:
            for src in hndl.iter_log_sources():
                by_addr[promtail_key].srv.sources.append(src)

        tail_log_key = f'{host}:tail_log'

        if tail_log_key in by_addr:
            for src in hndl.iter_log_sources():
                by_addr[tail_log_key].srv.paths.append(src['path'])

        for bal in hndl.l7_balancer():
            proto = bal['proto']
            srv = by_addr[f'{host}:balancer_{proto}'].srv

            for net in by_name[host]['net']:
                rec = {
                    'server': bal['server'],
                    'source': bal['source'],
                    'dest': 'http://' + net['ip'] + bal['dest'],
                }

                srv.real.append(rec)

    py_modules = list(sorted(frozenset(py_modules)))

    for h in hosts:
        srvs = by_host[h['hostname']]

        h['extra'] = '\n'.join(it_srvs(srvs, code, {'py_extra_modules': ':'.join(py_modules)}))

        for s in srvs:
            if s.disabled():
                h['disabled'].append(s.name())

    for h, ss in DISABLE.items():
        cconf['by_host'][h]['disabled'].extend(ss)

    return cconf


class _Unpickler(pickle.Unpickler):
    # Back-compat for old pickles with module='builtins' (pre-cg-anchoring).
    def find_class(self, module, name):
        try:
            return super().find_class(module, name)
        except AttributeError:
            return globals()[name]


if __name__ == '__main__':
    sys.modules.setdefault('cg', sys.modules[__name__])
    ctx = _Unpickler(io.BytesIO(base64.b64decode(sys.argv[1]))).load()['srv']
    getattr(ctx, sys.argv[2], lambda: None)(*sys.argv[3:])
