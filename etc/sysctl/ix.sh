{% extends '//die/gen.sh' %}

{# UDP/TCP buffer + softirq tuning for the 4-NIC link_join setup.
   - rmem_max/wmem_max bumped 16 MiB → 32 MiB so SO_*BUFFORCE=16MB
     in gofra (and 8 MiB in upstream nebula) actually take effect.
   - netdev_max_backlog default 1000 was overflowing under bursts
     of 200k+ pkt/sec from gofra's stripe across 4 NICs, showing
     up as Udp.RcvbufErrors growth on the receiver. 30000 covers
     a couple of seconds at full line rate per CPU.
   See lab/NET.md. #}

{% block install %}
mkdir -p ${out}/etc/sysctl.d

cat << EOF > ${out}/etc/sysctl.d/quic.conf
net.core.rmem_max = 33554432
net.core.wmem_max = 33554432
net.core.netdev_max_backlog = 30000
EOF
{% endblock %}
