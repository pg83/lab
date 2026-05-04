{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/gorn
bin/ghcr/event/scripts
{% endblock %}
