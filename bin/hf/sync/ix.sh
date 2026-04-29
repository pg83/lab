{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/hf/sync/cron
bin/hf/sync/client
bin/hf/sync/scripts
bin/mirror/fetch/scripts
bin/mc/gc/cron(root=/gorn/hf_sync,hours=2)
{% endblock %}
