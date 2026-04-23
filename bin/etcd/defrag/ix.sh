{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/etcd/ctl
bin/etcd/defrag/scripts
bin/etcd/defrag/cron
{% endblock %}
