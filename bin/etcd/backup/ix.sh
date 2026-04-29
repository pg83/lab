{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/etcd/ctl
bin/minio/patched/client
bin/zstd
bin/etcd/backup/scripts
bin/etcd/backup/cron
bin/mc/gc/cron(root=/gorn/backup,hours=24)
{% endblock %}
