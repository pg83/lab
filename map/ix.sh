{% extends '//die/hub.sh' %}

{% block run_deps %}
{{(cluster_map | des).by_host[hostname].extra}}

etc

bin/ci
bin/updater
bin/mc
bin/dev
bin/mtr
bin/ghcr
bin/htop
bin/ncdu
bin/iotop
bin/strace
bin/persdb
bin/tcpdump
bin/hf/sync
bin/ethtool
bin/sched/10
bin/sched/100
etc/host/keys
bin/ix/timeout
bin/sched/1000
bin/lm/sensors
bin/traceroute
bin/etcd/backup
bin/etcd/defrag
bin/kernel/6/14
bin/kernel/6/16
bin/mirror/fetch(socks5_proxy=127.0.0.1:{{(cluster_map | des).ports.socks_proxy}})
bin/ogorod/mirror
bin/smart/mon/tools
bin/fixits(delay=10)
bin/minio/iam/reconcile
bin/auto/update(user=ix)
bin/kernel/gengrub(kernel_boot_flags=rootdelay=20)

set/fs
set/stalix/server(fetcher_socks5_proxy=127.0.0.1:{{(cluster_map | des).ports.socks_proxy}})
{% endblock %}
