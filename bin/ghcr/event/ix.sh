{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/gorn
bin/python
bin/ghcr/event/scripts
{% endblock %}
