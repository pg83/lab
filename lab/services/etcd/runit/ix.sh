{% extends '//lab/services/persist/ix.sh' %}

{% set etcid = "etcd-cluster-2" %}

{% block all_etcd %}
{% for x in (cluster_map | des).etcd %}
{{x}}=http://{{x}}:2380
{% endfor %}
{% endblock %}

{% block srv_command %}
mkdir -p /home/{{srv_user}}/{{etcid}}

exec etcd \
    --name {{hostname}} \
    --data-dir /home/{{srv_user}}/{{etcid}} \
    --initial-advertise-peer-urls http://{{hostname}}:2380 \
    --listen-peer-urls http://0.0.0.0:2380 \
    --listen-client-urls http://0.0.0.0:2379 \
    --advertise-client-urls http://{{hostname}}:2379 \
    --initial-cluster-token {{etcid}}\
    --initial-cluster {{self.all_etcd() | lines | join(",")}} \
    --initial-cluster-state new
{% endblock %}
