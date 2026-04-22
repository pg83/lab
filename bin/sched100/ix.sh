{% extends '//die/hub.sh' %}

{#
  Fast-bucket diagnostics. Every 100s a runit service `sched100` iterates
  scripts from /etc/sched/100/ and logs the output to tinylog — queryable
  via `logcli query '{service="sched100"} |~ "<prefix>"'`.

  Pulls in bin/sched(delay=100) transitively through the collector hubs.
#}

{% block run_deps %}
lab/bin/sched/psi(delay=100)
lab/bin/sched/net/stat(delay=100)
lab/bin/sched/sock/stat(delay=100)
lab/bin/sched/load(delay=100)
{% endblock %}
