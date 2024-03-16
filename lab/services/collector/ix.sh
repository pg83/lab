{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/prometheus
lab/etc/user(user=collector)
lab/services/collector/config
lab/services/collector/runit(srv_dir=collector,srv_user=collector)
{% endblock %}
