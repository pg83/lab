{% extends '//die/hub.sh' %}

{% block run_deps %}
{{(cluster_map | des).by_host[hostname].extra}}

lab/etc
lab/services/autoupdate(user=ix)

bin/mc
bin/htop
bin/ix/tmpfs
etc/host/keys
bin/kernel/6/12
bin/kernel/6/14
bin/fixits(delay=10)
bin/kernel/gengrub(kernel_boot_flags=rootdelay=20)

set/fs
set/stalix/server(fetcher_socks5_proxy=localhost:8015)
{% endblock %}
