{% extends '//die/hub.sh' %}

{% set cluster_gen %}
def do(v):
    v['etcd'] = {
        'hosts': [x['hostname'] for x in v['hosts']][:3],
        'ports': {
            'client': v['ports']['etcd_client'],
            'peer': v['ports']['etcd_peer'],
        },
    }

    return v
{% endset %}

{% set cluster_map | jl | eval(cluster_gen) %}
{
    "hosts": [
        {
            "ip": "10.0.0.85",
            "hostname": "lab1"
        },
        {
            "ip": "10.0.0.251",
            "hostname": "lab2"
        },
        {
            "ip": "10.0.0.98",
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
        "proxy_http": 8080,
        "proxy_https": 8090,
        "prometheus": 9090,
        "node_exporter": 9100
    },
    "users": {
        "etcd": 1002,
        "mirror": 103
    }
}
{% endset %}

{% block run_deps %}
lab/map(cluster_map={{cluster_map | ser}})
{% endblock %}
