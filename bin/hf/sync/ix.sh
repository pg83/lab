{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/hf/sync/client
bin/hf/sync/scripts
bin/hf/sync/cron
bin/mirror/fetch/scripts
{% endblock %}
