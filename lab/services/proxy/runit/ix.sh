{% extends '//etc/services/runit/script/ix.sh' %}

{% block srv_command %}
export ETCDCTL_ENDPOINTS=localhost:2379
etcdctl lock proxy reproxy --static.enabled
{% endblock %}
