{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/etcd/ctl
bin/dedup/scripts
{% endblock %}
