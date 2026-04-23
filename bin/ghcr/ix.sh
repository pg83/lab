{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/oras
bin/python
bin/ghcr/cron
bin/ghcr/scripts
{% endblock %}
