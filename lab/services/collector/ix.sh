{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/prometheus
etc/user/nologin(userid=1001,user=collector)
lab/services/collector/config
lab/services/collector/runit(srv_dir=collector,srv_user=collector)
{% endblock %}
