{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/dropbear/runit/scripts/impl(srv_dir=dropbear)
{% endblock %}
