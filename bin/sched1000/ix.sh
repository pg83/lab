{% extends '//die/hub.sh' %}

{#
  Slow-bucket diagnostics. Every 1000s (~16m) a runit service `sched1000`
  iterates /etc/sched/1000/ and logs to tinylog — queryable via
  `logcli query '{service="sched1000"} |~ "<prefix>"'`.

  Collectors here are heavier (smartctl reads the drive, xfs_info opens
  the block device, ip route dumps can be big) — do NOT move them into
  sched100 without thought.
#}

{% block run_deps %}
lab/bin/sched/smart(delay=1000)
lab/bin/sched/disk/stat(delay=1000)
lab/bin/sched/df(delay=1000)
lab/bin/sched/ip/diag(delay=1000)
lab/bin/sched/xfs/info(delay=1000)
{% endblock %}
