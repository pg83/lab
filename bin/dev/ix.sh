{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/curl
bin/openssh/client
bin/etcd/ctl
bin/minio/patched/client
bin/dev/scripts
{% endblock %}
