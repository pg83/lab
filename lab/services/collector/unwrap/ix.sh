{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/etc/user
bin/prometheus
lab/services/collector/config
lab/services/collector/runit(srv_dir={{user}},srv_user={{user}})
{% endblock %}
