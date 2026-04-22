{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/grafana/reload/scripts(delay={{delay}},port={{port}},password={{password}})
bin/curl
{% endblock %}
