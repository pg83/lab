{% extends '//lab/services/persist/ix.sh' %}

{% block cluster_map %}
{{cluster_map | b64d}}
{% endblock %}

{% set my_ip %}{{(self.cluster_map() | jl | group_by("hostname"))[hostname][0]["ip"]}}{% endset %}

{% block all_etcd %}
{% for x in self.cluster_map() | jl %}
{{x["hostname"]}}=http://{{x["ip"]}}:2380
{% endfor %}
{% endblock %}

{% block srv_command %}
cd /home/etcd/

exec etcd \
    --name {{hostname}} \
    --initial-advertise-peer-urls http://{{my_ip}}:2380 \
    --listen-peer-urls http://{{my_ip}}:2380 \
    --listen-client-urls http://{{my_ip}}:2379,http://127.0.0.1:2379 \
    --advertise-client-urls http://{{my_ip}}:2379 \
    --initial-cluster-token etcd-cluster-2 \
    --initial-cluster {{','.join(ix.parse_list(self.all_etcd()))}} \
    --initial-cluster-state new
{% endblock %}
