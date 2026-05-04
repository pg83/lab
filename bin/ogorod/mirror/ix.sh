{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/gorn
bin/python
bin/etcd/ctl
bin/git/unwrap
bin/ogorod/mirror/scripts
bin/ci/hook
{% endblock %}
