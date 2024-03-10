{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/etcd
lab/services/vault
lab/services/ci(ci_targets=set/ci)
{% endblock %}
