{% extends '//die/gen.sh' %}

{# Deterministic ARP for multi-NIC same-subnet hosts. Each NIC only
   replies to ARP for IPs it actually owns, and outgoing ARPs use the
   MAC of the NIC whose IP is in the src field. Without this the
   kernel answers any ARP on any NIC and the L2 switch forwards
   traffic to whichever port happens to be cached in peers — physical
   multi-path bandwidth collapses. See lab/NET.md. #}

{% block install %}
mkdir -p ${out}/etc/sysctl.d

cat << EOF > ${out}/etc/sysctl.d/arp.conf
net.ipv4.conf.all.arp_ignore = 1
net.ipv4.conf.all.arp_announce = 2
net.ipv4.conf.default.arp_ignore = 1
net.ipv4.conf.default.arp_announce = 2
EOF
{% endblock %}
