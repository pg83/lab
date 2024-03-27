{% extends '//lab/services/persist/ix.sh' %}

{% set etcid = "etcd-cluster-2" %}
{% set cm = cluster_map | des %}

{% block all_etcd %}
{% for x in cm.etcd.hosts %}
{{x}}=http://{{x}}:{{cm.etcd.ports.peer}}
{% endfor %}
{% endblock %}

{% block srv_command %}
mkdir -p /home/{{srv_user}}/{{etcid}}

exec etcd \
    --name {{hostname}} \
    --data-dir /home/{{srv_user}}/{{etcid}} \
    --initial-advertise-peer-urls http://{{hostname}}:{{cm.etcd.ports.peer}} \
    --listen-peer-urls http://0.0.0.0:{{cm.etcd.ports.peer}} \
    --listen-client-urls http://0.0.0.0:{{cm.etcd.ports.client}} \
    --advertise-client-urls http://{{hostname}}:{{cm.etcd.ports.client}} \
    --initial-cluster-token {{etcid}} \
    --initial-cluster {{self.all_etcd() | lines | join(",")}} \
    --initial-cluster-state existing
{% endblock %}
