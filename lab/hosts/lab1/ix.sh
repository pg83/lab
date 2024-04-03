{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/ip(ip_addr=10.0.0.64/24,ip_iface=eth0,ip_gw=10.0.0.1)
lab/services/ip(ip_addr=10.0.0.65/24,ip_iface=eth1,ip_gw=10.0.0.1)
lab/services/ip(ip_addr=10.0.0.66/24,ip_iface=eth2,ip_gw=10.0.0.1)
lab/services/ip(ip_addr=10.0.0.67/24,ip_iface=eth3,ip_gw=10.0.0.1)
lab/services/mirror(mirror_rsync=1)
lab/services/ci(ci_targets=set/ci)
{% endblock %}
