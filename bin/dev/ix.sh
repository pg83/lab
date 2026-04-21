{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/curl
bin/python
bin/etcd/ctl
bin/dev/scripts
bin/openssh/client
bin/minio/patched/client
{% endblock %}
