{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/etcd
lab/services/vault
{% endblock %}
