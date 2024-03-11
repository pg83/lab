{% extends '//die/hub.sh' %}

{% block cluster_map %}
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
    ]
}
{% endblock %}

{% block run_deps %}
lab/map(cluster_map={{self.cluster_map() | b64e}})
{% endblock %}
