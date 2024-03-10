{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/prometheus
bin/prometheus/node/exporter
etc/user/nologin(userid=1001,user=collector)
etc/services/runit(srv_dir=node_exporter,srv_user=collector,srv_command=exec node_exporter)
lab/services/collector/config
lab/services/collector/runit(srv_dir=collector,srv_user=collector)
{% endblock %}
