{% extends '//die/hub.sh' %}

{# 10s-bucket diagnostics; cheap counters only. #}

{% block run_deps %}
bin/sched/udp/stat(delay=10)
bin/sched/tcp/stat(delay=10)
bin/sched/eth/stat(delay=10)
bin/sched/net/stat(delay=10)
bin/sched/tun/stat(delay=10)
bin/sched/proc/cpu(delay=10)
{% endblock %}
