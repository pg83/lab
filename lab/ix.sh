{% extends '//die/hub.sh' %}

{% set cluster_gen %}
def do(v):
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
{% endset %}

{% set cluster_map | jl | eval(cluster_gen) %}
{
    "hosts": [
        {
            "ip": "10.0.0.85",
            "hostname": "lab1",
            "disabled": ["etcd"]
        },
        {
            "ip": "10.0.0.251",
            "hostname": "lab2",
            "disabled": ["ci"]
        },
        {
            "ip": "10.0.0.160",
            "hostname": "lab3"
        }
    ],
    "ports": {
        "etcd_client": 2379,
        "etcd_peer": 2380,
        "torrent_webui": 8000,
        "ftpd": 8001,
        "sftpd": 8002,
        "mirror_http": 8003,
        "mirror_rsyncd": 8004,
        "webhook": 8005,
        "proxy_http": 8080,
        "proxy_https": 8090,
        "prometheus": 9090,
        "node_exporter": 9100
    },
    "users": {
        "mirror": 103,
        "ci": 104,
        "collector": 1001,
        "etcd": 1002,
        "node_exporter": 1003,
        "torrent": 1004,
        "sftp": 1005,
        "proxy": 1006,
        "git_lab": 1007,
        "git_ci": 1008,
        "hz": 1009,
        "webhook": 1010
    }
}
{% endset %}

{% block run_deps %}
lab/map(cluster_map={{cluster_map | ser}})
{% endblock %}
