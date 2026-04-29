{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/zstd
bin/python
bin/etcd/ctl
bin/etcd/backup/cron
bin/etcd/backup/scripts
bin/minio/patched/client
bin/mc/gc/cron(root=/gorn/backup,hours=24)
{% endblock %}
