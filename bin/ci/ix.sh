{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/gorn
bin/molot
bin/git/clone
bin/etcd/ctl
bin/ci/scripts
{% endblock %}
