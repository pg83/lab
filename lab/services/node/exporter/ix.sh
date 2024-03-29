{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
bin/prometheus/node/exporter
lab/etc/user(user=node_exporter)
etc/services/runit(srv_dir=node_exporter,srv_user=node_exporter,srv_command=exec node_exporter --web.listen-address=:{{cm.ports.node_exporter}})
{% endblock %}
