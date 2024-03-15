{% extends '//die/hub.sh' %}

{% set cluster_map | jl %}
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
    "etcd": {
        "hosts": [
            "lab1",
            "lab2",
            "lab3"
        ],
        "ports": {
            "client": {{self.etcd_client_port()}},
            "peer": {{self.etcd_peer_port()}}
        }
    },
    "ports": {
        "etcd_client": {% block etcd_client_port %}2379{% endblock %},
        "etcd_peer": {% block etcd_peer_port %}2380{% endblock %},
        "torrent_webui": 8000,
        "ftpd": 8001,
        "sftpd": 8002,
        "mirror_http": 8003,
        "proxy_http": 8080,
        "proxy_https": 8090,
        "prometheus": 9090,
        "node_exporter": 9100
    }
}
{% endset %}

{% block run_deps %}
lab/map(cluster_map={{cluster_map | ser}})
{% endblock %}
