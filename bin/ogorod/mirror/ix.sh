{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/etcd/ctl
bin/git/unwrap
bin/ogorod/mirror/cron
bin/ogorod/mirror/scripts
{% endblock %}
