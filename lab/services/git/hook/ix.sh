{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/etcd/ctl
lab/services/git/hook/scripts
{% endblock %}
