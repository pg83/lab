{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/oras
bin/python
bin/ghcr/scripts
{% endblock %}
