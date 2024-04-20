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
            'url': 'http://webhook.homelab.cam',
            'port': self.port,
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
        srv = Service(self, '')
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
    def __init__(self, host, port, smap, prom):
        self.host = host
        self.port = port
        self.smap = smap
        self.prom = prom

    def prom_port(self):
        return self.prom

    def user(self):
        return 'root'

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
            'hosts': list(self.smap.keys())
        }

        return cfg


class NebulaLh(Nebula):
    def __init__(self, host, port, smap, prom):
        self.host = host
        self.port = port
        self.smap = smap
        self.prom = prom

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
                '--directory', self.path,
                '--password', 'qwerty123',
                '--username', 'anon',
                '--sftpd-port', self.port,
            ]

            exec_into(*args, user=self.users()[1])


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

    def pkgs(self):
        yield {
            'pkg': 'bin/minio/patched',
        }

    def run(self):
        args = [
            'minio', 'server',
            '--address', self.addr,
            self.cmap,
        ]

        exec_into(*args, LAB_LOCAL_IP=self.ipv4)


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
            'pkg': 'bin/dropbear',
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
            yield f'--static.rule={x["vhost"]},/,{x["real"]}'

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


class ClusterMap:
    def __init__(self, conf):
        self.conf = conf

    def it_cluster(self):
        p = self.conf['ports']

        neb_map = {}
        bal_map = []
        all_etc = []

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

            all_etc.append(hn)

            yield {
                'host': hn,
                'serv': Etcd(all_etc, p['etcd_peer'], p['etcd_client'], hn),
            }

            yield {
                'host': hn,
                'serv': DropBear(h['nebula']['ip'], p['sshd']),
            }

            for i in []:
                cmap = 'http://lab{1...3}.eth{1...3}/mnt/minio'

                yield {
                    'host': hn,
                    'serv': MinIO(i, h['net'][i]['ip'], p['minio'], cmap),
                }

            yield {
                'host': hn,
                'serv': Ssh3(p['ssh_3']),
            }

            yield {
                'host': hn,
                'serv': HZ(),
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

            yield {
                'host': hn,
                'serv': NebulaNode(hn, p['nebula_node'], neb_map, p['nebula_node_prom']),
            }

            if lh := h.get('nebula', {}).get('lh', None):
                lh_port = p['nebula_lh']
                neb_reals = list(it_nebula_reals(lh, h, lh_port))
                neb_map[lh['vip']] = list(f'{h}:{p}' for h, p in neb_reals)

                yield {
                    'host': hn,
                    'serv': NebulaLh(lh['name'], lh_port, neb_map, p['nebula_lh_prom']),
                }

        tp = '/home/torrent/profiles/qBittorrent/downloads'

        for hn in ['lab2']:
            yield {
                'host': hn,
                'serv': SftpD(p['sftp_d'], tp)
            }


HZ_SCRIPT = '''
sleep 60
date | /etc/hooks/git_ci.sh
sleep 60
date | /etc/hooks/git_lab.sh
'''


class HZ:
    def run(self):
        with memfd('script') as ss:
            with open(ss, 'w') as f:
                f.write(HZ_SCRIPT)

            exec_into('etcdctl', 'lock', 'hz', '--', '/bin/sh', ss)


sys.modules['builtins'].WebHooks = WebHooks
sys.modules['builtins'].IPerf = IPerf
sys.modules['builtins'].NodeExporter = NodeExporter
sys.modules['builtins'].Collector = Collector
sys.modules['builtins'].NebulaNode = NebulaNode
sys.modules['builtins'].NebulaLh = NebulaLh
sys.modules['builtins'].Ssh3 = Ssh3
sys.modules['builtins'].SftpD = SftpD
sys.modules['builtins'].HZ = HZ
sys.modules['builtins'].MinIO = MinIO
sys.modules['builtins'].DropBear = DropBear
sys.modules['builtins'].BalancerHttp = BalancerHttp
sys.modules['builtins'].Etcd = Etcd


def exec_into(*args, user=None, **kwargs):
    args = [str(x) for x in args]

    if user:
        args = ['su-exec', user] + args

    env = os.environ.copy()

    for k, v in kwargs.items():
        env[str(k)] = str(v)

    os.execvpe(args[0], args, env)


RUN_PY = '''
import sys
import zlib
import base64
import pickle
ctx = '__CTX__'
ctx = base64.b64decode(ctx)
ctx = zlib.decompress(ctx)
ctx = pickle.loads(ctx)
exec(ctx['code'])
ctx = pickle.loads(ctx['data'])
getattr(ctx['obj'], sys.argv[1], lambda: None)()
'''


def gen_runner(code, srv):
    ctx = {
        'obj': srv,
    }

    ctx = {
        'code': code,
        'data': pickle.dumps(ctx)
    }

    runpy = pickle.dumps(ctx)
    runpy = zlib.compress(runpy)
    runpy = base64.b64encode(runpy).decode()
    runpy = RUN_PY.replace('__CTX__', runpy)
    runpy = base64.b64encode(runpy.encode()).decode()

    return runpy


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
    def __init__(self, srv, code):
        self.srv = srv
        self.code = code

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

    def run_py(self):
        return {
            'pkg': 'lab/services/py',
            'srv_dir': self.name(),
            'runpy_script': gen_runner(self.code, self.srv),
            'srv_user': self.user(),
        }

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

        yield self.run_py()


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
        'disabled': [],
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


def it_srvs(srvs):
    for s in srvs:
        for x in s.serialize():
            yield to_srv(**x)


def do(code):
    hosts = [gen_host(h) for h in (1, 2, 3)]

    for x in hosts:
        x['ip'] = x['net'][0]['ip']
        x['disabled'].append('dhcpcd')

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
        'proxy_http': 8080,
        'proxy_https': 8090,
    }

    users = {
        'mirror': 103,
        'ci': 104,
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
        hndl = Service(rec['serv'], code)
        host = rec['host']
        addr = host + ':' + hndl.name()

        by_host[host].append(hndl)
        by_addr[addr] = hndl

        for job in hndl.prom_jobs():
            by_addr[f'{host}:collector'].srv.jobs.append(job)

        for bal in hndl.l7_balancer():
            proto, vhost = bal['url'].split('://')
            srv = by_addr[f'{host}:balancer_{proto}'].srv

            for net in by_name[host]['net']:
                rec = {
                    'vhost': vhost,
                    'real': 'http://' + net['ip'] + ':' + str(bal['port']),
                }

                srv.real.append(rec)

    for h in hosts:
        srvs = by_host[h['hostname']]

        h['extra'] = '\n'.join(it_srvs(srvs))

        for s in srvs:
            if s.disabled():
                h['disabled'].append(s.name())

    # cconf['by_host']['lab2']['disabled'].append('etcd')

    return cconf
