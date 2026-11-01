{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/cas
bin/git/unwrap
bin/make
bin/python
bin/event
bin/etcd/ctl
bin/etcd/lock
bin/mirror/fetch/scripts
bin/minio/patched/client
{% endblock %}
