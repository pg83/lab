{% extends '//die/hub.sh' %}

{# 1000s-bucket diagnostics; heavier collectors (smartctl, xfs_info). #}

{% block run_deps %}
bin/sched/smart(delay=1000)
bin/sched/disk/stat(delay=1000)
bin/sched/df(delay=1000)
bin/sched/ip/diag(delay=1000)
bin/sched/xfs/info(delay=1000)
{% endblock %}
