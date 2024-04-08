{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/nebula/daemon
lab/services/nebula/lh/runit(srv_dir=nebula_lh)
{% endblock %}
