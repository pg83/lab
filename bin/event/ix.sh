{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/etcd/ctl
bin/event/scripts

bin/ci/hook
bin/mirror/fetch/event
bin/hf/sync/event
bin/ghcr/event
{% endblock %}
