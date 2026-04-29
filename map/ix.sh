{% extends '//die/hub.sh' %}

{% block run_deps %}
{{(cluster_map | des).by_host[hostname].extra}}

etc

bin/ci
bin/mc
bin/dev
bin/mtr
bin/mc/gc
bin/ghcr
bin/htop
bin/persdb
bin/hf/sync
bin/ix/tmpfs
etc/host/keys
bin/sched/10
bin/sched/100
bin/ix/timeout
bin/sched/1000
bin/lm/sensors
bin/traceroute
bin/etcd/backup
bin/etcd/defrag
bin/kernel/6/14
bin/kernel/6/16
bin/mirror/fetch
bin/ogorod/mirror
bin/smart/mon/tools
bin/mc/gc/cron(root=/gorn/cli,hours=24)
bin/fixits(delay=10)
bin/auto/update(user=ix)
bin/kernel/gengrub(kernel_boot_flags=rootdelay=20)

set/fs
set/stalix/server(fetcher_socks5_proxy=127.0.0.1:8015)
{% endblock %}
