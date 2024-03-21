{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
lab/services/cgi(cgi_user=webhook,cgi_port={{cm.ports.webhook}},cgi_dir=/etc/hooks/)
{% endblock %}
