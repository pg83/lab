import os
import sys
import zlib
import time
import json
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

        cfg['static_host_map'] = self.smap

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

        cfg['listen'] = {
            'host': '0.0.0.0',
            'port': self.port,
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

        cfg['static_host_map'] = self.smap

        cfg['tun'] = {
            'disabled': True,
        }

        cfg['lighthouse'] = {
            'am_lighthouse': True,
        }

        cfg['listen'] = {
            'host': '0.0.0.0',
            'port': self.port,
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
        ]

        exec_into(*args)


def it_nebula_reals(lh, h, port):
    yield lh['ip'], lh['port']

    for n in h['net']:
        yield n['ip'], port


def nebula_smap(hosts, lh_port):
    lhs = dict()

    for h in hosts:
        if lh := h.get('nebula', {}).get('lh', None):
            lhs[lh['vip']] = list(f'{h}:{p}' for h, p in it_nebula_reals(lh, h, lh_port))

    return lhs


class ClusterMap:
    def __init__(self, conf):
        self.conf = conf

    def it_cluster(self):
        p = self.conf['ports']

        neb_map = nebula_smap(self.conf['hosts'], p['nebula_lh'])

        for h in self.conf['hosts']:
            hn = h['hostname']

            yield {
                'host': hn,
                'serv': Collector(p['collector']),
            }

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

            yield {
                'host': hn,
                'serv': NebulaNode(hn, p['nebula_node'], neb_map, p['nebula_node_prom']),
            }

            if lh := h.get('nebula', {}).get('lh', None):
                yield {
                    'host': hn,
                    'serv': NebulaLh(lh['name'], p['nebula_lh'], neb_map, p['nebula_lh_prom']),
                }


sys.modules['builtins'].WebHooks = WebHooks
sys.modules['builtins'].IPerf = IPerf
sys.modules['builtins'].NodeExporter = NodeExporter
sys.modules['builtins'].Collector = Collector
sys.modules['builtins'].NebulaNode = NebulaNode
sys.modules['builtins'].NebulaLh = NebulaLh
sys.modules['builtins'].Ssh3 = Ssh3


def exec_into(*args, **kwargs):
    args = [str(x) for x in args]
    env = os.environ.copy()

    for k, v in kwargs.items():
        env[str(k)] = str(v)

    os.execvpe(args[0], args, env)


RUN_PY = '''
import zlib
import base64
import pickle
ctx = '__CTX__'
ctx = base64.b64decode(ctx)
ctx = zlib.decompress(ctx)
ctx = pickle.loads(ctx)
exec(ctx['code'])
ctx = pickle.loads(ctx['data'])
getattr(ctx['obj'], ctx['meth'])(*ctx.get('args', []), **ctx.get('kwargs', {}))
'''


def gen_runner(code, srv):
    ctx = {
        'obj': srv,
        'meth': 'run',
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


def cluster_conf(code):
    hosts = [gen_host(h) for h in (1, 2, 3)]

    ports = {
        'etcd_client': 2379,
        'etcd_peer': 2380,
        'nebula_lh': 4242,
        'nebula_node': 4243,
        'torrent_webui': 8000,
        'ftpd': 8001,
        'sftpd': 8002,
        'mirror_http': 8003,
        'mirror_rsyncd': 8004,
        'web_hooks': 8005,
        'i_perf': 8006,
        'node_exporter': 8007,
        'collector': 8008,
        'nebula_node_prom': 8009,
        'nebula_lh_prom': 8010,
        'ssh_3': 8011,
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
        'sftp': 1005,
        'proxy': 1006,
        'git_lab': 1007,
        'git_ci': 1008,
        'hz': 1009,
        'web_hooks': 1010,
        'i_perf': 1011,
        'nebula_lh': 1012,
    }

    cconf = {
        'hosts': hosts,
        'ports': ports,
        'users': users,
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

    for h in hosts:
        srvs = by_host[h['hostname']]

        h['extra'] = '\n'.join(it_srvs(srvs))

        for s in srvs:
            if s.disabled():
                h['disabled'].append(s.name())

    return cconf


def gen_cluster(v):
    for x in v['hosts']:
        if 'ip' not in x:
            x['ip'] = x['net'][0]['ip']

        if 'net' in x:
            x['disabled'].append('dhcpcd')

    ep = v['ports']['etcd_client']

    etcd = {
        'hosts': [x['hostname'] for x in v['hosts']][:3],
        'ports': {
            'client': ep,
            'peer': v['ports']['etcd_peer'],
        },
    }

    etcd['ep'] = ','.join(f'{x}:{ep}' for x in etcd['hosts'])

    v['etcd'] = etcd

    by_host = {}

    for h in v['hosts']:
        by_host[h['hostname']] = h

    v['by_host'] = by_host

    return v


def do(code):
    return gen_cluster(cluster_conf(code))
