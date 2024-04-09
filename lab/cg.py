import sys
import time
import pickle
import base64
import collections


class Service:
    def __init__(self, tout):
        self.tout = tout

    def name(self):
        return 'sleeper'

    def run(self):
        while True:
            print(self.tout)
            time.sleep(self.tout)


class ClusterMap:
    def __init__(self, conf):
        self.conf = conf

    def it_cluster(self):
        for h in self.conf['hosts']:
            yield h['hostname'], Service(1)


sys.modules['builtins'].Service = Service


RUN_PY = '''
import base64
import pickle
ctx = '__CTX__'
ctx = base64.b64decode(ctx)
ctx = pickle.loads(ctx)
exec(ctx['code'])
ctx = pickle.loads(ctx['data'])
getattr(ctx['obj'], ctx['meth'])(*ctx.get('args', []), **ctx.get('kwargs', {}))
'''


def to_srv(pkg='', **args):
    if args:
        return pkg + '(' + ','.join(f'{x}={y}' for x, y in args.items()) + ')'

    return pkg


def it_config(code, o):
    ctx = {
        'obj': o,
        'meth': 'run',
    }

    ctx = {
        'code': code,
        'data': pickle.dumps(ctx)
    }

    runpy = base64.b64encode(pickle.dumps(ctx)).decode()
    runpy = RUN_PY.replace('__CTX__', runpy)
    runpy = base64.b64encode(runpy.encode()).decode()

    yield {
        'pkg': 'lab/services/py',
        'srv_dir': o.name(),
        'runpy_script': runpy,
    }


def to_config(code, o):
    return '\n'.join(to_srv(**x) for x in it_config(code, o)).strip() + '\n'


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
        'webhook': 8005,
        'iperf': 8006,
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
        'webhook': 1010,
    }

    cconf = {
        'hosts': hosts,
        'ports': ports,
        'users': users,
    }

    by_host = collections.defaultdict(list)

    for host, service in ClusterMap(cconf).it_cluster():
        by_host[host].append(service)

    for h in hosts:
        h['extra'] = '\n'.join(to_config(code, srv) for srv in by_host[h['hostname']]) + '\n'

    return cconf


def gen_cluster(v):
    for x in v['hosts']:
        if 'disabled' not in x:
            x['disabled'] = []

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
