{% extends '//die/gen.sh' %}

{# UDP/TCP buf+softirq; zz- prefix wins concat over upstream quic.conf. #}

{% block install %}
mkdir -p ${out}/etc/sysctl.d

cat << EOF > ${out}/etc/sysctl.d/zz-link-join.conf
net.core.rmem_max = 33554432
net.core.wmem_max = 33554432
net.core.netdev_max_backlog = 30000
EOF

{# DPI en route drops TCP state without RST; stock 2h keepalives leave
   long-lived tunnels (cloudflared) blind on half-open sockets. #}
cat << EOF > ${out}/etc/sysctl.d/zz-tcp-keepalive.conf
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 15
net.ipv4.tcp_keepalive_probes = 4
EOF
{% endblock %}
