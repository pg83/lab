{% extends '//etc/services/runit/script/ix.sh' %}

{% set cm = cluster_map | des %}

{% block srv_command %}
export ETCDCTL_ENDPOINTS=localhost:{{cm.etcd.ports.client}}

(
while true; do
    sleep 150
    echo 'hz has been saved'
    etcdctl put /git/logs/git_hz
    date
done
) > hz
{% endblock %}
