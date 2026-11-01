{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/gorn
bin/molot
bin/etcd/lock
bin/git/unwrap
bin/git/passenv
bin/updater/merger/scripts
{% endblock %}
