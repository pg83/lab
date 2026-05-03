{% extends '//die/gen.sh' %}

{# Deterministic ARP per-NIC; else L2 collapses multi-path. lab/NET.md. #}

{% block install %}
mkdir -p ${out}/etc/sysctl.d

cat << EOF > ${out}/etc/sysctl.d/arp.conf
net.ipv4.conf.all.arp_ignore = 1
net.ipv4.conf.all.arp_announce = 2
net.ipv4.conf.default.arp_ignore = 1
net.ipv4.conf.default.arp_announce = 2
EOF
{% endblock %}
