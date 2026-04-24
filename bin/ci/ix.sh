{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/gorn
bin/molot
bin/dedup
bin/python
bin/ci/cron
bin/etcd/ctl
bin/git/unwrap
bin/ci/scripts
bin/minio/patched/client
{% endblock %}
