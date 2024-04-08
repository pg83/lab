{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/nebula/daemon
lab/services/nebula/node/runit(srv_dir=nebula_node)
{% endblock %}
