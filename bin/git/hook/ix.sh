{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/etcd/ctl
bin/git/hook/scripts
{% endblock %}
