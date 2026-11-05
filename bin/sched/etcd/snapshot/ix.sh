{% extends '//die/hub.sh' %}

{# Once per delay: a snapshot of this host's member of an etcd on its own partition. #}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/etcd/snapshot/scripts(delay={{delay}},etcd_name={{etcd_name}},etcd_part={{etcd_part}},etcd_port={{etcd_port}})
bin/etcd/ctl
bin/zstd
bin/gptfdisk
{% endblock %}
