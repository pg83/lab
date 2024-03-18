{% extends '//etc/services/runit/script/ix.sh' %}

{% set cm = cluster_map | des %}

{% block srv_command %}
export ETCDCTL_ENDPOINTS="{{cm.etcd.ep}}"
sleep 150
date | etcdctl put /git/logs/git_hz
{% endblock %}
