{% extends '//die/gen.sh' %}

{# UDP/TCP buffer + softirq tuning for the 4-NIC link_join setup.

   IMPORTANT: filename is `zz-link-join.conf`, NOT `quic.conf`. Two
   packages writing the same filename in etc/sysctl.d/ collide at
   IX-realm-assembly time (last package wins, deterministic but
   surprising) — bin/runit/sys/etc lays down its own quic.conf with
   rmem_max=2.5 MiB and that was silently winning over our 16 MiB.

   etc/concat cat's etc/sysctl.d/* in alphabetical order into
   /etc/sysctl, then `sysctl -p /etc/sysctl` runs at boot. Later
   lines for the same key override earlier ones, so naming this
   `zz-…` puts our values *after* upstream's quic.conf in the
   concat output and our settings stick.

   Values:
   - rmem_max/wmem_max: 16 MiB → 32 MiB so SO_*BUFFORCE=16 MiB in
     gofra (and 8 MiB in upstream nebula) actually take effect.
   - netdev_max_backlog: 1000 → 30000 — covers ~2s of full line
     rate per CPU, plenty for stripe bursts. The default was
     producing Udp.RcvbufErrors growth on the receiver during
     iperf3 over the gofra tunnel.

   See lab/NET.md. #}

{% block install %}
mkdir -p ${out}/etc/sysctl.d

cat << EOF > ${out}/etc/sysctl.d/zz-link-join.conf
net.core.rmem_max = 33554432
net.core.wmem_max = 33554432
net.core.netdev_max_backlog = 30000
EOF
{% endblock %}
