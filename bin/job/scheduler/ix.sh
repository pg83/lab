{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/etcd/ctl
bin/ix/timeout
bin/job/scheduler/scripts
{% endblock %}
