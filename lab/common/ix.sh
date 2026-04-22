{% extends '//die/hub.sh' %}

{% block run_deps %}
{{(cluster_map | des).by_host[hostname].extra}}

lab/etc
lab/services/autoupdate(user=ix)

bin/mc
bin/htop
bin/dev
bin/ix/tmpfs
etc/host/keys
bin/lm/sensors
bin/kernel/6/14
bin/kernel/6/16
bin/smart/mon/tools
bin/ix/timeout
bin/fixits(delay=10)
bin/sched/100
bin/sched/1000
bin/kernel/gengrub(kernel_boot_flags=rootdelay=20)
set/fs
set/stalix/server(fetcher_socks5_proxy=localhost:8015)
{% endblock %}
