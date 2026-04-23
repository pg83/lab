{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/gorn
bin/molot
bin/python
bin/etcd/ctl
bin/git/clone
bin/minio/patched/client
bin/ci/scripts
{% endblock %}
