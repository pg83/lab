{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/etcd/ctl
lab/services/git/hook
lab/services/git/cgi/scripts
{% endblock %}
