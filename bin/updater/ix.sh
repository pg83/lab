{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/gorn
bin/molot
bin/etcd/lock
bin/git/unwrap
bin/git/passenv
bin/minio/patched/client
bin/updater/scripts
bin/updater/fixer
{% endblock %}
