{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}
{% set hm = cm.by_host[hostname] %}

{% block run_deps %}
etc/env
etc/arp
etc/keys
etc/hosts
etc/sysctl
etc/multihome

{% for d in hm.disabled %}
etc/stopper(srv_dir={{d}})
{% endfor %}

{% for net in hm.net %}
etc/ip(ip_addr={{net.ip}}/{{net.nm}},ip_gw={{net.gw}},ip_iface={{net.if}})
{% endfor %}

etc/core
etc/concat
etc/user/ix
etc/user/root
{% endblock %}
