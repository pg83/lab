{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/etcd/ctl
bin/etcd/defrag/cron
bin/etcd/defrag/scripts
bin/mc/gc/cron(root=/gorn/etcd_defrag,hours=1)
{% endblock %}
