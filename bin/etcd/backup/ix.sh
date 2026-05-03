{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/zstd
bin/python
bin/etcd/ctl
bin/etcd/backup/scripts
bin/minio/patched/client
{% endblock %}
