#!/usr/bin/env python3

import os
import sys
import zlib
import time
import json
import shutil
import pickle
import base64
import contextlib
import subprocess
import collections


DISABLE = {
    'lab1': ['minio_1', 'minio_2', 'minio_3', 'ci'],
    'lab2': [],
    'lab3': [],
}


CI_MAP = {
    'lab1': 'set/ci',
    'lab2': 'set/ci/tier/1',
    'lab3': 'set/ci/tier/0',
}


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
    def __init__(self, port):
        self.port = port
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
    cmd = ['etcdctl', 'get', '--print-value-only', k]

    return subprocess.check_output(cmd)


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

            print(cfg, file=sys.stderr)

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
    timeout connect 5000
    timeout client 50000
    timeout server 50000

listen socks5
    bind :{port}
    mode tcp
    balance roundrobin
    server server1 lab2.local:8014
    server server2 lab3.local:8014
'''


def haproxy_conf_parts(port, addrs):
    yield HA_CONF.replace('{port}', str(port))

    for n, addr in enumerate(addrs):
        yield f'    server server{n} {addr}'


class SocksProxy:
    def __init__(self, port, addrs):
        self.p = port
        self.a = addrs

    def pkgs(self):
        yield {
            'pkg': 'bin/haproxy',
        }

    def conf(self):
        return '\n'.join(haproxy_conf_parts(self.p, self.a)).strip() + '\n'

    def run(self):
        print(self.conf())

        with memfd('haproxy.conf') as path:
            with open(path, 'w') as f:
                f.write(self.conf())

            exec_into('haproxy', '-f', path)


class SshTunnel:
    def __init__(self, port, addr, keyn, user):
        self.port = port
        self.addr = addr
        self.keyn = keyn
        self._usr = user
        self.v = 1

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

        args = [
            'ssh', '-q',
            '-o', 'StrictHostKeyChecking no',
            '-i', 'key',
            '-D', self.port,
            '-N',
            self.addr,
        ]

        exec_into(*args)


TORRENT_PREPARE = '''
set -xue
btrfs device scan
btrfs device scan /dev/sda /dev/sdb /dev/sdc
mkdir -p /var/mnt/torrent
mount /dev/sda /var/mnt/torrent
'''


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
        subprocess.run(['/bin/sh'], input=TORRENT_PREPARE.encode())

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
                '--directory', self.path,
                '--password', 'qwerty123',
                '--username', 'anon',
                '--sftpd-port', self.port,
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
                'MINIO_ROOT_USER': 'qwerty',
                'MINIO_ROOT_PASSWORD': 'qwerty123',
                'MINIO_BROWSER': 'off',
            }

            exec_into(*args, **kwargs)


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


SECOND_IP = '''
set -x
ip addr del {addr} dev eth0
etcdctl lock {addr} /bin/sh -- -c "ip addr add {addr} dev eth0; sleep 1000"
'''


class SecondIP:
    def __init__(self, addr):
        self.addr = addr

    def name(self):
        return 'ip_' + self.addr.replace('.', '_').replace('/', '_')

    def user(self):
        return 'root'

    def run(self):
        with memfd('script') as fn:
            with open(fn, 'w') as f:
                f.write(SECOND_IP.replace('{addr}', self.addr))

            exec_into('/bin/sh', fn)


class BalancerHttp:
    def __init__(self, port, real):
        self.port = port
        self.real = real

    def pkgs(self):
        yield {
            'pkg': 'bin/reproxy',
        }

    def it_args(self):
        yield 'reproxy'
        yield f'--listen=0.0.0.0:{self.port}'
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


class Etcd:
    def __init__(self, peers, port_peer, port_client, hostname):
        self.etcid = 'etcd-cluster-2'
        self.peers = peers
        self.port_peer = port_peer
        self.port_client = port_client
        self.hostname = hostname

    def prepare(self):
        make_dirs('/home/etcd', owner='etcd')

    def pkgs(self):
        yield {
            'pkg': 'bin/etcd/server',
        }

    @property
    def data_dir(self):
        return f'/home/etcd/{self.etcid}'

    def it_all(self):
        for x in self.peers:
            yield f'{x}=http://{x}:{self.port_peer}'

    def run(self):
        os.makedirs(self.data_dir, exist_ok=True)

        args = [
            'etcd',
            '--name', self.hostname,
            '--data-dir', self.data_dir,
            '--initial-advertise-peer-urls',
            f'http://{self.hostname}:{self.port_peer}',
            '--listen-peer-urls',
            f'http://0.0.0.0:{self.port_peer}',
            '--listen-client-urls',
            f'http://0.0.0.0:{self.port_client}',
            '--advertise-client-urls',
            f'http://{self.hostname}:{self.port_client}',
            '--initial-cluster-token',
            self.etcid,
            '--initial-cluster',
            ','.join(self.it_all()),
            '--initial-cluster-state',
            'existing',
        ]

        exec_into(*args)


CI_SCRIPT = '''
set -xue
mkdir -p {wd}
/bin/mount_ci {wd}
mkdir -p {wd}/ix_root
rm -rf {wd}/ix_root/trash {wd}/ix_root/build
chown {user}:{user} {wd}/ix_root
chown {user}:{user} /var/run/{user}
exec su-exec {user} /bin/ci_cycle
'''


class CI:
    def __init__(self, targets):
        self.targets = targets

    def name(self):
        return 'ci'

    def users(self):
        return [
            'root',
            self.name(),
        ]

    def wd(self):
        return '/var/run/' + self.name() + '/mount'

    def pkgs(self):
        yield {
            'pkg': 'lab/services/ci',
            'wd': self.wd(),
            'ci_targets': self.targets,
        }

    def run(self):
        s = CI_SCRIPT

        s = s.replace('{user}', self.name())
        s = s.replace('{wd}', self.wd())

        with memfd('script') as ss:
            with open(ss, 'w') as f:
                f.write(s)

            args = [
                '/bin/unshare', '-m',
                '/bin/sh', ss
            ]

            exec_into(*args)


class ClusterMap:
    def __init__(self, conf):
        self.conf = conf

    def it_cluster(self):
        p = self.conf['ports']

        neb_map = {}
        bal_map = []
        all_etc = []
        all_s5s = []

        for h in self.conf['hosts']:
            hn = h['hostname']

            yield {
                'host': hn,
                'serv': Collector(p['collector']),
            }

            yield {
                'host': hn,
                'serv': BalancerHttp(p['proxy_http'], bal_map),
            }

            yield {
                'host': hn,
                'serv': SecondIP('10.0.0.32/24'),
            }

            yield {
                'host': hn,
                'serv': SecondIP('10.0.0.33/24'),
            }

            all_etc.append(hn)

            yield {
                'host': hn,
                'serv': Etcd(all_etc, p['etcd_peer'], p['etcd_client'], hn),
            }

            yield {
                'host': hn,
                'serv': DropBear(h['nebula']['ip'], p['sshd']),
            }

            yield {
                'host': hn,
                'serv': SshTunnel(
                    '0.0.0.0:' + str(p['ssh_aws_tunnel']),
                    'ec2-user@13.50.197.102',
                    'aws_key',
                    'ssh_aws_tunnel',
                ),
            }

            all_s5s.append(hn + ':' + str(p['ssh_aws_tunnel']))

            yield {
                'host': hn,
                'serv': SocksProxy(p['socks_proxy'], all_s5s),
            }

            if False:
                yield {
                    'host': hn,
                    'serv': DropBear2(23),
                }

            mio_cmap = 'http://lab{1...3}.eth{1...3}/var/mnt/minio/my/data'

            def mio_srv(i):
                return MinIO(i, h['net'][i]['ip'], p['minio'], mio_cmap)

            minios = [mio_srv(i) for i in (1, 2, 3)]

            for m in minios:
                yield {
                    'host': hn,
                    'serv': m,
                }

            mc_host = h['nebula']['ip']
            mc_port = p['minio_web']
            mc_serv = 'http://' + minios[0].addr

            yield {
                'host': hn,
                'serv': MinioConsole(mc_host, mc_port, mc_serv),
            }

            if False:
                yield {
                    'host': hn,
                    'serv': Ssh3(p['ssh_3']),
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

        tp = '/var/mnt/torrent/profiles/qBittorrent/downloads'

        for hn in ['lab2']:
            yield {
                'host': hn,
                'serv': SftpD(p['sftp_d'], tp),
            }

        for hn, path in CI_MAP.items():
            yield {
                'host': hn,
                'serv': CI(path),
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
sys.modules['builtins'].Etcd = Etcd
sys.modules['builtins'].MinioConsole = MinioConsole
sys.modules['builtins'].SecondIP = SecondIP
sys.modules['builtins'].DropBear2 = DropBear2
sys.modules['builtins'].CI = CI
sys.modules['builtins'].SshTunnel = SshTunnel
sys.modules['builtins'].SocksProxy = SocksProxy


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
                'xiaomi_passwd': 'qwerty123',
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


def it_srvs(srvs, code):
    for x in it_pkgs(srvs, code):
        yield to_srv(**x)


def do(code):
    hosts = [gen_host(h) for h in (1, 2, 3)]

    for x in hosts:
        x['ip'] = x['net'][0]['ip']

    ports = {
        'sshd': 22,
        'etcd_client': 2379,
        'etcd_peer': 2380,
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
        'ssh_aws_tunnel': 8014,
        'socks_proxy': 8015,
        'proxy_http': 8080,
        'proxy_https': 8090,
    }

    users = {
        'collector': 1001,
        'etcd': 1002,
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
        'ci': 1017,
        'minio_console': 1018,
        'pf': 1019,
        'ssh_aws_tunnel': 1020,
        'socks_proxy': 1021,
    }

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

    for rec in ClusterMap(cconf).it_cluster():
        hndl = Service(rec['serv'])
        host = rec['host']
        addr = host + ':' + hndl.name()

        by_host[host].append(hndl)
        by_addr[addr] = hndl

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

    for h in hosts:
        srvs = by_host[h['hostname']]

        h['extra'] = '\n'.join(it_srvs(srvs, code))

        for s in srvs:
            if s.disabled():
                h['disabled'].append(s.name())

    for h, ss in DISABLE.items():
        cconf['by_host'][h]['disabled'].extend(ss)

    return cconf


if __name__ == '__main__':
    ctx = pickle.loads(base64.b64decode(sys.argv[1]))
    getattr(ctx, sys.argv[2], lambda: None)(*sys.argv[3:])
