{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/ci/metrics/cron
bin/ci/metrics/scripts
{% endblock %}
