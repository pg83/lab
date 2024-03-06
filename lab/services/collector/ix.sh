{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/prometheus
lab/services/collector/scripts
etc/user/nologin(userid=1001,user=collector)
etc/services/runit(srv_dir=collector,srv_user=collector,srv_command=exec collectd)
{% endblock %}
