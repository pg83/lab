{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/ci/metrics/cron
bin/ci/metrics/scripts
bin/mc/gc/cron(root=/gorn/ci_metrics,hours=24)
{% endblock %}
