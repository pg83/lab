{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/oras
bin/python
bin/ghcr/cron
bin/ghcr/scripts
bin/mc/gc/cron(root=/gorn/ghcr_sync,hours=1)
{% endblock %}
