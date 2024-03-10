{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/etcd
lab/services/vault
lab/services/mirror
lab/services/ci(ci_targets=set/ci/tier/1)
{% endblock %}
