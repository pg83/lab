#!/usr/bin/env python3

import os
import sys
import zlib
import time
import json
import shutil
import pickle
import base64
import random
import contextlib
import subprocess
import collections

import urllib.request as ur


DISABLE_ALL = [
    #'drop_bear_2',
]

DISABLE = {
    'lab1': DISABLE_ALL + [],
    'lab2': DISABLE_ALL + [],
    'lab3': DISABLE_ALL + [],
}

CI_TIERS = [
    'set/ci/tier/0',
    'set/ci/tier/1',
    'set/ci/tier/2',
]

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


class WebHooks:
    def __init__(self, port, where):
        self.port = port
        self.path = where

    def l7_balancer(self):
        yield {
            'proto': 'http',
            'server': 'webhook.homelab.cam',
            'source': '^/(.*)',
            'dest': f':{self.port}/$1',
        }

        yield {
            'proto': 'http',
            'server': 'ix.homelab.cam',
            'source': '^/(.*)',
            'dest': f':{self.port}/cas.sh?$1',
        }

    def run(self):
        exec_into('cgi_server', f'0.0.0.0:{self.port}', self.path)

    def pkgs(self):
        yield {
            'pkg': 'bin/cgi/server'
        }

        yield {
            'pkg': 'bin/git/hook',
            'evlog_topic': 'git_ci',
        }

        yield {
            'pkg': 'bin/git/hook',
            'evlog_topic': 'git_lab',
        }

        yield {
            'pkg': 'bin/mirror/serve',
        }


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
        exec_into('node_exporter', f'--web.listen-address=:{self.port}')


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
                # Stamped on every sample so federation preserves
                # per-host origin; without this, all three Collectors
                # would produce {instance="localhost:<port>", ...} and
                # the federator would dedupe them into one series.
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


class Nebula:
    def pkgs(self):
        yield {
            'pkg': 'bin/nebula/daemon',
        }

    def run(self):
        with multi(memfd("conf"), memfd("ca"), memfd("cert"), memfd("key")) as (conf, ca, cert, key):
            cfg = self.config()

            cfg['static_host_map'] = self.smap

            cfg['listen'] = {
                'host': '0.0.0.0',
                'port': self.port,
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
                f.write(get_key('/nebula/ca.crt'))

            with open(cert, 'wb') as f:
                f.write(get_key(f'/nebula/{self.host}.crt'))

            with open(key, 'wb') as f:
                f.write(get_key(f'/nebula/{self.host}.key'))

            exec_into('nebula', '--config', conf)


class NebulaNode(Nebula):
    def __init__(self, host, port, smap, prom, advr):
        self.host = host
        self.port = port
        self.smap = smap
        self.prom = prom
        self.advr = advr

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
    bind :{port}
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
        self.v = 1
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
                '--s3-endpoint', 'http://10.0.0.65:8012/',
                '--s3-region', 'minio',
                '--s3-access-key', get_key('/s3/user').decode().strip(),
                '--s3-access-secret', get_key('/s3/password').decode().strip(),
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
mkdir -p /var/mnt/minio/my
mount -t xfs LABEL=MINIO_{n} /var/mnt/minio/my
mkdir -p /var/mnt/minio/my/data
chown {user} /var/mnt/minio/my/data
exec su-exec {user} minio server --address {addr} {cmap}
'''


class MinIO:
    def __init__(self, uniq, ipv4, port, cmap):
        self.v = 1
        self.ipv4 = ipv4
        self.port = port
        self.uniq = uniq
        self.cmap = cmap

    @property
    def addr(self):
        return f'{self.ipv4}:{self.port}'

    def name(self):
        return f'minio_{self.uniq}'

    def users(self):
        return [
            'root',
            self.name(),
        ]

    def pkgs(self):
        yield {
            'pkg': 'bin/minio/patched',
        }

        yield {
            'pkg': 'bin/su/exec',
        }

    def run(self):
        s = MINIO_SCRIPT

        s = s.replace('{n}', str(self.uniq))
        s = s.replace('{addr}', self.addr)
        s = s.replace('{cmap}', self.cmap)
        s = s.replace('{user}', self.name())

        with memfd('script') as ss:
            with open(ss, 'w') as f:
                f.write(s)

            args = [
                '/bin/unshare', '-m',
                '/bin/sh', ss
            ]

            kwargs = {
                'LAB_LOCAL_IP': self.ipv4,
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

    def user(self):
        return 'root'

    def pkgs(self):
        yield {
            'pkg': 'bin/dropbear/2024',
        }

    def run(self):
        subprocess.run(['/bin/sh'], input=DB_PREPARE.encode())

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
        self.v = 4
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
            'pkg': 'lab/etc/user/home',
            'user': self.name(),
            'user_home': self.home_dir(),
        }

    def home_dir(self):
        return f'{self.std_dir()}/home'

    def prepare(self):
        u = self.name()
        make_dirs(self.home_dir(), owner=u)
        ssh_dir = f'{self.home_dir()}/.ssh'
        make_dirs(ssh_dir, owner=u)
        os.chmod(ssh_dir, 0o700)
        make_dirs(f'{self.std_dir()}/log', owner=u)

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
            'pkg': 'lab/etc/user/home',
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
                'endpoints': [],
            },
            's3': {
                'endpoint': self.s3['endpoint'],
                'region': self.s3['region'],
                'bucket': self.s3['bucket'],
                'access_key': get_key('/s3/user').decode().strip(),
                'secret_key': get_key('/s3/password').decode().strip(),
                'use_path_style': self.s3.get('use_path_style', True),
            },
        }

    def run(self):
        cfg = self.config()

        with memfd('conf') as fn:
            with open(fn, 'w') as f:
                f.write(json.dumps(cfg))

            exec_into('gorn', self.subcommand(), '--config', fn, user=self.name(), PATH='/bin')


class Gorn(GornBase):
    def __init__(self, endpoints, s3):
        self.v = 4
        self.endpoints = endpoints
        self.s3 = s3

    def name(self):
        return 'gorn'

    def subcommand(self):
        return 'serve'

    def config(self):
        return self.base_config()


class GornCtl(GornBase):
    def __init__(self, endpoints, s3, listen):
        self.v = 2
        self.endpoints = endpoints
        self.s3 = s3
        self.listen = listen

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
    def __init__(self, endpoints, s3, port):
        self.v = 1
        self.endpoints = endpoints
        self.s3 = s3
        self.port = port

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
        self.v = 1
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


SECOND_IP = '''
set -x
ip addr del {addr} dev eth0
exec etcdctl lock /lock/{name} -- /bin/sh -c "set -xue; ip addr add {addr} dev eth0; sleep 1000"
'''


class SecondIP:
    def __init__(self, addr):
        self.addr = addr
        self.script = SECOND_IP
        self.v = 1

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

            exec_into('/bin/sh', fn)


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
    def __init__(self, peers, port_peer, port_client, hostname, etcid, addr, user_name):
        self.v = 2
        self.etcid = etcid
        self.peers = peers
        self.port_peer = port_peer
        self.port_client = port_client
        self.hostname = hostname
        self.addr = addr
        self.user_name = user_name

    def name(self):
        return self.user_name

    def user(self):
        return self.user_name

    def prepare(self):
        make_dirs(f'/home/{self.user_name}', owner=self.user_name)

    def pkgs(self):
        yield {
            'pkg': 'bin/etcd/server',
        }

    @property
    def data_dir(self):
        return f'/home/{self.user_name}/{self.etcid}'

    def it_all(self):
        for x in self.peers:
            yield f'{x["hostname"]}=http://{x["ip"]}:{self.port_peer}'

    def prom_jobs(self):
        yield {
            'job_name': self.name(),
            'static_configs': [{'targets': [f'{self.addr}:{self.port_client}']}],
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
            f'http://{self.addr}:{self.port_peer}',
            '--listen-peer-urls',
            f'http://{self.addr}:{self.port_peer}',
            '--listen-client-urls',
            f'http://{self.addr}:{self.port_client}',
            '--advertise-client-urls',
            f'http://{self.addr}:{self.port_client}',
            '--initial-cluster-token',
            self.etcid,
            '--initial-cluster',
            ','.join(self.it_all()),
            '--initial-cluster-state',
            'existing',
            # Drop revisions older than 1h so MVCC history doesn't
            # balloon past the 2GiB quota during long build runs.
            '--auto-compaction-mode', 'periodic',
            '--auto-compaction-retention', '1h',
            # Give 8GiB of headroom; compaction keeps the live set
            # small, this is only so a burst won't trip the alarm
            # before the next compaction tick.
            '--quota-backend-bytes', str(8 * 1024 * 1024 * 1024),
        ]

        exec_into(*args)


class CI:
    def __init__(self, idx, targets, gorn_api, s3_endpoint):
        self.v = 2
        self.idx = idx
        self.targets = targets
        self.gorn_api = gorn_api
        self.s3_endpoint = s3_endpoint

    def name(self):
        return f'ci_{self.idx}'

    def pkgs(self):
        yield {
            'pkg': 'lab/services/ci',
            'ci_targets': self.targets,
        }

    def run(self):
        exec_into(
            '/bin/ci_cycle',
            GORN_API=self.gorn_api,
            S3_ENDPOINT=self.s3_endpoint,
            MOLOT_FULL_SLOTS='10',
            AWS_ACCESS_KEY_ID=get_key('/s3/user').decode().strip(),
            AWS_SECRET_ACCESS_KEY=get_key('/s3/password').decode().strip(),
        )


class Perses:
    def __init__(self, port):
        self.v = 1
        self.port = port

    def name(self):
        return 'perses'

    def home_dir(self):
        return f'/var/run/{self.name()}/std/home'

    def pkgs(self):
        yield {
            'pkg': 'bin/perses',
        }

        yield {
            'pkg': 'lab/etc/user/home',
            'user': self.name(),
            'user_home': self.home_dir(),
        }

    def prepare(self):
        make_dirs(f'{self.home_dir()}/data', owner=self.name())

    def prom_port(self):
        return self.port

    def config(self):
        return {
            'database': {
                'file': {
                    'folder': f'{self.home_dir()}/data',
                    'extension': 'json',
                },
            },
            'security': {
                'enable_auth': False,
            },
        }

    def run(self):
        with memfd('config.yaml') as fn:
            with open(fn, 'w') as f:
                f.write(json.dumps(self.config()))

            exec_into('perses', '-config', fn, f'-web.listen-address=:{self.port}')


class Federator:
    # Cluster-wide aggregator: scrapes /federate on every host's local
    # Collector and serves a unified view. Grafana points here instead
    # of at its local Collector so dashboards see the whole cluster,
    # and cross-host queries (sum by host, compare latency, etc.) work
    # directly. One per host — no SPOF.
    def __init__(self, port, collector_port, hosts):
        self.v = 1
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
                    'metrics_path': '/federate',
                    'params': {'match[]': ['{job=~".+"}']},
                    'static_configs': [
                        {
                            'targets': [f'{h}.nebula:{self.collector_port}' for h in self.hosts],
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
                f'--web.listen-address=127.0.0.1:{self.port}',
            ]

            exec_into(*args)


class Grafana:
    def __init__(self, port, collector_port):
        self.v = 1
        self.port = port
        self.collector_port = collector_port

    def name(self):
        return 'grafana'

    def state_dir(self):
        return f'/var/run/{self.name()}'

    def pkgs(self):
        yield {
            'pkg': 'bin/grafana',
        }

        yield {
            'pkg': 'aux/grafana',
            'collector_port': str(self.collector_port),
        }

        yield {
            'pkg': 'bin/sched/grafana/reload',
            'delay': '10',
            'port': str(self.port),
        }

    def ini(self):
        s = self.state_dir()

        return (
            '[server]\n'
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
        )

    def run(self):
        # Grafana's plugin loader does a symlink-escape containment check
        # (filepath.Rel against realpath) and rejects anything whose
        # canonical path escapes the homepath. In the realm, only files
        # are symlinked (directories are real) — so realpath() on any
        # dir stops at the rlm-system store, while every leaf inside
        # still links back to bin-grafana-ui and escapes containment.
        # Resolve a known leaf (conf/sample.ini) and strip the two
        # trailing components to land on the concrete bin-grafana-ui
        # share/grafana dir.
        sample = os.path.realpath('/ix/realm/system/share/grafana/conf/sample.ini')
        homepath = os.path.dirname(os.path.dirname(sample))

        with memfd('grafana.ini') as fn:
            with open(fn, 'w') as f:
                f.write(self.ini())

            exec_into('grafana', 'server', '--config', fn, '--homepath', homepath)


class Samogon:
    # SFTP daemon over a MinIO-backed content-addressable store.
    # /torrents/torrents/<infohash> holds the .torrent blob, pieces
    # land at /torrents/pieces/<piece-hash>. Read-only — fetches are
    # kicked from elsewhere via `gorn ignite -- samogon fetch <b64>`.
    def __init__(self, port, s3_endpoint):
        self.v = 1
        self.port = port
        self.s3_endpoint = s3_endpoint

    def name(self):
        return 'samogon'

    def users(self):
        # First element is the uid runit starts the service as; keeping
        # root there lets run() read /etc/keys before dropping to the
        # service user via su-exec. Same dance as SftpD.
        return ['root', 'samogon']

    def home_dir(self):
        return f'/var/run/{self.name()}/std/home'

    def pkgs(self):
        yield {
            'pkg': 'bin/samogon',
        }

        yield {
            'pkg': 'lab/etc/user/home',
            'user': 'samogon',
            'user_home': self.home_dir(),
        }

    def prepare(self):
        make_dirs(self.home_dir(), owner='samogon')

    def run(self):
        # Copy host key into a memfd while still root; the memfd fd
        # is inherited across su-exec, so the samogon user reads key
        # material it couldn't touch on disk.
        with memfd('host_key') as hk:
            with open(hk, 'w') as f:
                f.write(open('/etc/keys/ssh_ed25519').read())

            # cwd becomes samogon's writable scratch — storage.go
            # does `mkdtemp(".", "mc-samogon-")` for the mc config
            # dir, and /var/run/<name>/std (the default runsrv cwd)
            # is root-owned tinylog space.
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
                'AWS_ACCESS_KEY_ID': get_key('/s3/user').decode().strip(),
                'AWS_SECRET_ACCESS_KEY': get_key('/s3/password').decode().strip(),
                'S3_ENDPOINT': self.s3_endpoint,
                'S3_BUCKET': 'samogon',
                'SAMOGON_S3_ROOT': 'torrents',
            }

            exec_into(*args, user='samogon', **env)


class Secrets:
    def __init__(self, port):
        self.v = 5
        self.port = port

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

        exec_into(*args)


class PersDB:
    def __init__(self, port):
        self.v = 4
        self.port = port

    def name(self):
        return 'pers_db'

    def users(self):
        return [
            'root',
        ]

    def pkgs(self):
        yield {
            'pkg': 'bin/persdb',
        }

    def run(self):
        args = [
            'ix_serve_persdb',
            self.port,
        ]

        exec_into(*args)


class CO2Mon:
    def __init__(self, port):
        self.v = 1
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


class MirrorFetch:
    def __init__(self):
        self.v = 2

    def pkgs(self):
        yield {
            'pkg': 'bin/mirror/fetch',
        }

    def run(self):
        env = {
            'HOME': os.getcwd(),
            'TMPDIR': os.getcwd(),
            'PATH': '/bin',
        }

        time.sleep(random.random() * 10)

        exec_into('etcdctl', 'lock', '/lock/mirror', 'cache_ix_sources', **env)


class HFSync:
    def __init__(self):
        self.v = 1

    def name(self):
        return 'hf_sync'

    def pkgs(self):
        yield {
            'pkg': 'bin/hf/sync',
        }

    def py_modules(self):
        return [
            'pip/tqdm',
            'pip/PyYAML',
            'pip/requests',
            'pip/filelock',
        ]

    def run(self):
        env = {
            'PATH': '/bin',
            'HF_TOKEN': get_key('/hf/token').decode().strip(),
            'HOME': os.getcwd(),
            'TMPDIR': os.getcwd(),
        }

        time.sleep(random.random() * 10)

        exec_into('etcdctl', 'lock', '/lock/hf', 'hf_sync', **env)


class GHCRSync:
    def __init__(self):
        self.v = 2

    def name(self):
        return 'ghcr_sync'

    def pkgs(self):
        yield {
            'pkg': 'bin/ghcr',
        }

    def run(self):
        env = {
            'PATH': '/bin',
            'GHCR_TOKEN': get_key('/ghcr/token').decode().strip(),
            'HOME': os.getcwd(),
            'TMPDIR': os.getcwd(),
        }

        time.sleep(random.random() * 10)

        exec_into('etcdctl', 'lock', '/lock/ghcr', 'ghcr_sync', **env)


class ClusterMap:
    def __init__(self, conf):
        self.conf = conf

    def it_cluster(self):
        p = self.conf['ports']

        neb_map = {}
        bal_map = []
        all_etc_private = []

        for hn in ['lab1', 'lab2', 'lab3']:
            h = self.conf['by_host'][hn]
            nb = h['nebula']

            all_etc_private.append({
                'hostname': hn,
                'ip': nb['ip'],
            })

            yield {
                'host': hn,
                'serv': EtcdPrivate(
                    all_etc_private,
                    p['etcd_peer_private'],
                    p['etcd_client_private'],
                    hn,
                    'secrets',
                    nb['ip'],
                    'etcd_private',
                ),
            }

        for hn in ['lab1', 'lab2', 'lab3']:
            h = self.conf['by_host'][hn]
            nb = h['nebula']
            mio_cmap = 'http://lab{1...3}.eth{1...3}/var/mnt/minio/my/data'

            def mio_srv(i):
                return MinIO(i, h['net'][i]['ip'], p['minio'], mio_cmap)

            minios = [mio_srv(i) for i in (1, 2, 3)]

            for m in minios:
                yield {
                    'host': hn,
                    'serv': m,
                }

            mc_host = nb['ip']
            mc_port = p['minio_web']
            mc_serv = 'http://' + minios[0].addr

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
                'serv': HFSync(),
            }

            yield {
                'host': hn,
                'serv': GHCRSync(),
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
                'serv': Perses(p['perses']),
            }

            yield {
                'host': hn,
                'serv': Federator(p['federator'], p['collector'], [x['hostname'] for x in self.conf['hosts']]),
            }

            yield {
                'host': hn,
                'serv': Grafana(p['grafana'], p['federator']),
            }

            yield {
                'host': hn,
                'serv': CO2Mon(p['co2_mon']),
            }

            yield {
                'host': hn,
                'serv': Secrets(p['secrets']),
            }

            yield {
                'host': hn,
                'serv': Samogon(
                    p['samogon'],
                    s3_endpoint=f"http://{hn}.eth1:{p['minio']}",
                ),
            }

            yield {
                'host': hn,
                'serv': PersDB(p['pers_db']),
            }

            yield {
                'host': hn,
                'serv': MirrorFetch(),
            }

            yield {
                'host': hn,
                'serv': BalancerHttp(p['proxy_http'], p['proxy_http_mgmt'], bal_map),
            }

            yield {
                'host': hn,
                'serv': SecondIP('10.0.0.32/24'),
            }

            yield {
                'host': hn,
                'serv': SecondIP('10.0.0.33/24'),
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
                        '0.0.0.0:' + str(p[k]),
                        tun['addr'],
                        tun['keyn'],
                        k,
                        tun['port'],
                        tun['tout'],
                    ),
                }

                all_s5s.append(hn + ':' + str(p[k]))

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
                'serv': WebHooks(p['web_hooks'], '/etc/hooks/'),
            }

            yield {
                'host': hn,
                'serv': NodeExporter(p['node_exporter']),
            }

            nn_port = p['nebula_node']
            nn_adv = [x['ip'] + f':{nn_port}' for x in h['net']]

            yield {
                'host': hn,
                'serv': NebulaNode(hn, nn_port, neb_map, p['nebula_node_prom'], nn_adv),
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

        for hn in self.conf['by_host']:
            for i, path in enumerate(CI_TIERS):
                yield {
                    'host': hn,
                    'serv': CI(
                        i,
                        path,
                        gorn_api=f"http://127.0.0.1:{p['gorn_ctl']}",
                        s3_endpoint=f"http://{hn}.eth1:{p['minio']}",
                    ),
                }

        gorn_endpoints = []

        for hn, n in GORN_N.items():
            h = self.conf['by_host'][hn]
            nb = h['nebula']

            for i in range(n):
                port = p[f'gorn_{i}']
                user = f'gorn_{i}'

                yield {
                    'host': hn,
                    'serv': GornSsh(i, nb['ip'], port, nb['hostname']),
                }

                gorn_endpoints.append({
                    'host': nb['ip'],
                    'port': port,
                    'user': user,
                    'path': f'/var/run/{user}/std/home',
                    'log_path': f'/var/run/{user}/std/log/agent.log',
                    'nebula_host': nb['hostname'],
                })

        for hn in GORN_N:
            h = self.conf['by_host'][hn]

            s3 = {
                'endpoint': f"http://{h['net'][1]['ip']}:{p['minio']}",
                'region': 'minio',
                'bucket': 'gorn',
                'use_path_style': True,
            }

            yield {
                'host': hn,
                'serv': Gorn(gorn_endpoints, s3),
            }

            yield {
                'host': hn,
                'serv': GornCtl(gorn_endpoints, s3, f"127.0.0.1:{p['gorn_ctl']}"),
            }

            yield {
                'host': hn,
                'serv': GornCtlNebula(gorn_endpoints, s3, f"{h['nebula']['ip']}:{p['gorn_ctl_nb']}"),
            }

            yield {
                'host': hn,
                'serv': GornWeb(f"http://127.0.0.1:{p['gorn_ctl']}", f"{h['nebula']['ip']}:{p['gorn_web']}"),
            }

            yield {
                'host': hn,
                'serv': GornProm(gorn_endpoints, s3, p['gorn_prom']),
            }


sys.modules['builtins'].IPerf = IPerf
sys.modules['builtins'].WebHooks = WebHooks
sys.modules['builtins'].NodeExporter = NodeExporter
sys.modules['builtins'].Collector = Collector
sys.modules['builtins'].NebulaNode = NebulaNode
sys.modules['builtins'].NebulaLh = NebulaLh
sys.modules['builtins'].Ssh3 = Ssh3
sys.modules['builtins'].SftpD = SftpD
sys.modules['builtins'].MinIO = MinIO
sys.modules['builtins'].DropBear = DropBear
sys.modules['builtins'].BalancerHttp = BalancerHttp
sys.modules['builtins'].EtcdPrivate = EtcdPrivate
sys.modules['builtins'].MinioConsole = MinioConsole
sys.modules['builtins'].SecondIP = SecondIP
sys.modules['builtins'].DropBear2 = DropBear2
sys.modules['builtins'].GornSsh = GornSsh
sys.modules['builtins'].Gorn = Gorn
sys.modules['builtins'].GornCtl = GornCtl
sys.modules['builtins'].GornCtlNebula = GornCtlNebula
sys.modules['builtins'].GornWeb = GornWeb
sys.modules['builtins'].GornProm = GornProm
sys.modules['builtins'].Perses = Perses
sys.modules['builtins'].Grafana = Grafana
sys.modules['builtins'].Federator = Federator
sys.modules['builtins'].CI = CI
sys.modules['builtins'].SshTunnel = SshTunnel
sys.modules['builtins'].SocksProxy = SocksProxy
sys.modules['builtins'].CO2Mon = CO2Mon
sys.modules['builtins'].MirrorFetch = MirrorFetch
sys.modules['builtins'].Samogon = Samogon
sys.modules['builtins'].Secrets = Secrets
sys.modules['builtins'].PersDB = PersDB
sys.modules['builtins'].HFSync = HFSync
sys.modules['builtins'].GHCRSync = GHCRSync
sys.modules['builtins'].Heat = Heat


def exec_into(*args, user=None, **kwargs):
    args = [str(x) for x in args]

    if user:
        args = ['su-exec', user] + args

    env = os.environ.copy()

    for k, v in kwargs.items():
        env[str(k)] = str(v)

    os.execvpe(args[0], args, env)


def gen_runner(srv):
    ctx = base64.b64encode(pickle.dumps(srv)).decode()
    scr = 'exec runpy ' + ctx + ' ${@}'

    return base64.b64encode(scr.encode()).decode()


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
        try:
            yield from self.srv.pkgs()
        except AttributeError:
            pass

        for user in self.users():
            yield {
                'pkg': 'lab/etc/user',
                'user': user,
            }

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

        yield {
            'pkg': 'lab/services/sh',
            'srv_dir': self.name(),
            'runsh_script': gen_runner(self.srv),
            'srv_user': self.user(),
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
    hosts = [gen_host(h) for h in (1, 2, 3, 4)]

    for x in hosts:
        x['ip'] = x['net'][0]['ip']

    ports = {
        'sshd': 22,
        'nebula_lh': 4242,
        'nebula_node': 4243,
        'torrent_webui': 8000,
        'ftpd': 8001,
        'sftp_d': 8002,
        'mirror_http': 8003,
        'mirror_rsyncd': 8004,
        'web_hooks': 8005,
        'i_perf': 8006,
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
        'perses': 8014,
        'proxy_http': 8080,
        'proxy_http_mgmt': 8081,
        'proxy_https': 8090,
        'etcd_client_private': 8020,
        'etcd_peer_private': 8021,
        'secrets': 8022,
        'sshd_rec': 8023,
        'pers_db': 8024,
        'grafana': 8029,
        'federator': 8030,
        'samogon': 8031,
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
        'web_hooks': 1010,
        'i_perf': 1011,
        'nebula_lh': 1012,
        'minio_1': 1013,
        'minio_2': 1014,
        'minio_3': 1015,
        'mirror': 1016,
        'minio_console': 1018,
        'pf': 1019,
        'socks_proxy': 1021,
        'ssh_cz_tunnel': 1023,
        'ssh_jopa_tunnel': 1024,
        'mirror_fetch': 1025,
        'etcd_private': 1026,
        'secrets': 1027,
        'hf_sync': 1028,
        'ghcr_sync': 1029,
        'perses': 1017,
        'grafana': 1094,
        'federator': 2000,
        'samogon': 2001,
    }

    for i in range(0, 64):
        users['heat_' + str(i + 1)] = 1030 + i

    for i in range(len(CI_TIERS)):
        users[f'ci_{i}'] = 1200 + i

    users['gorn'] = 1099
    users['gorn_ctl'] = 1098
    users['gorn_web'] = 1097
    users['gorn_ctl_nb'] = 1096
    users['gorn_prom'] = 1095
    ports['gorn_ctl'] = 8025
    ports['gorn_web'] = 8026
    ports['gorn_ctl_nb'] = 8027
    ports['gorn_prom'] = 8028

    gorn_max = max(GORN_N.values(), default=0)

    for i in range(gorn_max):
        ports[f'gorn_{i}'] = 9000 + i
        users[f'gorn_{i}'] = 1100 + i

    by_name = dict()

    for h in hosts:
        by_name[h['hostname']] = h

    cconf = {
        'hosts': hosts,
        'ports': ports,
        'users': users,
        'by_host': by_name,
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

    # Second pass — routing/registration lookups need by_addr fully populated
    # (e.g. EtcdPrivate is yielded before Collector, but has prom_jobs now).
    for host, hndl in hndl_by_host:
        for job in hndl.prom_jobs():
            by_addr[f'{host}:collector'].srv.jobs.append(job)

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


if __name__ == '__main__':
    ctx = pickle.loads(base64.b64decode(sys.argv[1]))
    getattr(ctx, sys.argv[2], lambda: None)(*sys.argv[3:])
