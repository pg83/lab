{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/prometheus/node/exporter
etc/user/nologin(userid=1003,user=node_exporter)
etc/services/runit(srv_dir=node_exporter,srv_user=node_exporter,srv_command=exec node_exporter)
{% endblock %}
