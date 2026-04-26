{% extends '//die/hub.sh' %}

{#
  10s-bucket diagnostics. Every 10s a runit service `sched10` iterates
  scripts from /etc/sched/10/ and logs the output to tinylog — queryable
  via `logcli query '{service="sched10"} |~ "<prefix>"'`.

  Pulls in bin/sched(delay=10) transitively through the collector hubs.
  Use this bucket only for cheap counters that benefit from
  high-frequency sampling (Udp.RcvbufErrors during link_join bursts,
  etc); heavier diagnostics belong in sched100 / sched1000.
#}

{% block run_deps %}
bin/sched/udp/stat(delay=10)
bin/sched/tcp/stat(delay=10)
bin/sched/eth/stat(delay=10)
bin/sched/net/stat(delay=10)
{% endblock %}
