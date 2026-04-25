{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/git/unwrap
bin/etcd/ctl
bin/ogorod/mirror/scripts
bin/ogorod/mirror/cron
{% endblock %}
