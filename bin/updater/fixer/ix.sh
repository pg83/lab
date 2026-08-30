{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/gorn
bin/molot
bin/etcd/lock
bin/git/unwrap
bin/git/passenv
bin/minio/patched/client
bin/ix/timeout
bin/codex/wrap
bin/openssl
bin/etcd/ctl
bin/ix/tools/regen
bin/updater/scripts
bin/updater/fixer/scripts
{% endblock %}
