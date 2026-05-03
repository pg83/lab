{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/zstd
bin/tar
bin/etcd/server
bin/etcd/wrap/scripts
bin/minio/patched/client
{% endblock %}
