import os
import sys
import zlib
import time
import pickle
import base64
import subprocess
import collections


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
            'pkg': 'lab/services/git/hook',
            'evlog_topic': 'git_ci',
        }

        yield {
            'pkg': 'lab/services/git/hook',
            'evlog_topic': 'git_lab',
        }


class ClusterMap:
    def __init__(self, conf):
        self.conf = conf

    def it_cluster(self):
        p = self.conf['ports']

        for h in self.conf['hosts']:
            hn = h['hostname']

            yield {
                'host': hn,
                'serv': IPerf(p['i_perf']),
            }

            yield {
                'host': hn,
                'serv': WebHooks(p['web_hooks'], '/etc/hooks/'),
            }


sys.modules['builtins'].WebHooks = WebHooks
sys.modules['builtins'].IPerf = IPerf


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
        'proxy_http': 8080,
        'proxy_https': 8090,
        'prometheus': 9090,
        'node_exporter': 9100,
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
        'sleeper': 1012,
    }

    cconf = {
        'hosts': hosts,
        'ports': ports,
        'users': users,
    }

    by_host = collections.defaultdict(list)

    for rec in ClusterMap(cconf).it_cluster():
        by_host[rec['host']].append(Service(rec['serv'], code))

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
