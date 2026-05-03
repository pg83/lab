{% extends '//die/hub.sh' %}

{# 100s-bucket diagnostics. #}

{% block run_deps %}
bin/sched/psi(delay=100)
bin/sched/net/stat(delay=100)
bin/sched/sock/stat(delay=100)
bin/sched/load(delay=100)
bin/sched/iostat(delay=100)
{% endblock %}
