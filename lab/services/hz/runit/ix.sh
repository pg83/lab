{% extends '//etc/services/runit/script/ix.sh' %}

{% set cm = cluster_map | des %}

{% block srv_command %}
export ETCDCTL_ENDPOINTS="{{cm.etcd.ep}}"
exec etcdctl lock hz -- /bin/sh ${PWD}/locked
{% endblock %}

{% block install %}
{{super()}}
cat << EOF > locked
sleep 60
date | etcdctl put /git/logs/git_ci
sleep 60
date | etcdctl put /git/logs/git_lab
EOF
{% endblock %}
