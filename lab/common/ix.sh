{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}
{% set hm = cm.by_host[hostname] %}

{% block run_deps %}
# there will be dragons
{{hm.extra}}

lab/etc

{% for net in cm.by_host[hostname].net %}
lab/services/ip(ip_addr={{net.ip}}/{{net.nm}},ip_gw={{net.gw}},ip_iface={{net.if}})
{% endfor %}

{% if hostname in cm.etcd.hosts %}
lab/services/etcd
lab/services/proxy(proxy_ip=10.0.0.32,proxy_port={{cm.ports.proxy_http}})
lab/services/proxy(proxy_ip=10.0.0.33,proxy_port={{cm.ports.proxy_https}},proxy_https=1)
{% endif %}

lab/services/autoupdate(user=ix)

lab/services/hz

bin/mc
bin/htop
bin/gengrub
bin/kernel/6/8
bin/kernel/6/7
bin/dropbear/runit

bin/fixits(delay=10)

set/fs
set/stalix/server
{% endblock %}
