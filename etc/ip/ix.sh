{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/runit/1.d

cat << EOF > ${out}/etc/runit/1.d/20-{{ip_iface}}.sh
ip addr add {{ip_addr}} dev {{ip_iface}}
ip link set {{ip_iface}} up
route add default gw {{ip_gw}} {{ip_iface}}
resolvconf -u
EOF
{% endblock %}
