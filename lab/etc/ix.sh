{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}
{% set hm = cm.by_host[hostname] %}

{% block run_deps %}
lab/etc/env
lab/etc/keys
lab/etc/hosts

{% for d in hm.disabled %}
lab/etc/stopper(srv_dir={{d}})
{% endfor %}

{% for net in hm.net %}
lab/etc/ip(ip_addr={{net.ip}}/{{net.nm}},ip_gw={{net.gw}},ip_iface={{net.if}})
{% endfor %}
{% endblock %}
