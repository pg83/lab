{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/su/exec
bin/prometheus
bin/prometheus/node/exporter
lab/services/collector/scripts
etc/user/nologin(userid=1001,user=collector)
etc/services/runit(srv_dir=collector,srv_command=exec collectd)
etc/services/runit(srv_dir=node_exporter,srv_user=collector,srv_command=exec node_exporter)
{% endblock %}
