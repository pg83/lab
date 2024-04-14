{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}
{% set hm = cm.by_host[hostname] %}

{% block run_deps %}
# there will be dragons
{{hm.extra}}

lab/etc

{% if hostname in cm.etcd.hosts %}
lab/services/etcd
{% endif %}

lab/services/autoupdate(user=ix)
lab/services/proxy(proxy_ip=10.0.0.32,proxy_port={{cm.ports.proxy_http}})
lab/services/proxy(proxy_ip=10.0.0.33,proxy_port={{cm.ports.proxy_https}},proxy_https=1)

bin/mc
bin/htop
bin/gengrub
etc/host/keys
bin/kernel/6/8
bin/kernel/6/7
bin/dropbear/runit
bin/fixits(delay=10)

set/fs
set/stalix/server
{% endblock %}
