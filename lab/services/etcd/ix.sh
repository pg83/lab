{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/etcd/unwrap(user=etcd)
{% endblock %}
