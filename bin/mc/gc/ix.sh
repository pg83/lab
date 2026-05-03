{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/mc/gc/cron(root=/gorn/mc_gc,hours=1)
{% endblock %}
