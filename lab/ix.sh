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
            "client": 2380,
            "peer": 2379
        }
    }
}
{% endset %}

{% block run_deps %}
lab/map(cluster_map={{cluster_map | ser}})
{% endblock %}
