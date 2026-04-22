{% extends '//die/gen.sh' %}

{# Persist per-uid policy routing used by multi-home MinIO.
   Drops a stage-1 init script that, after NICs are up (runs after
   20-<iface>.sh), programs three routing tables + matching rules:

     - table per minio_N uid (1013→eth1, 1014→eth2, 1015→eth3),
       each scoped to 10.0.0.0/24 with src = that NIC's address
     - uidrange rule per uid — catches minio's own outbound
     - `from <src>` rule per NIC — catches anything else that
       explicitly binds to that NIC's IP (iperf, mc, etc.)

   Self-sufficient: pulls per-host NIC list from cluster_map, bakes
   IPs in at render time → generated script is fully static, no
   runtime ip-addr lookup. Uses /ix/realm/ip/bin/ip because the
   busybox applet lacks `uidrange`.

   See lab/NET.md Option A for rationale. #}

{% set cm = cluster_map | des %}
{% set hm = cm.by_host[hostname] %}

{% block install %}
mkdir -p ${out}/etc/runit/1.d

cat << 'EOF' > ${out}/etc/runit/1.d/30-multihome.sh
IP=/ix/realm/ip/bin/ip
{% for net in hm.net if net.if != 'eth0' %}

$IP route replace 10.0.0.0/24 dev {{net.if}} src {{net.ip}} table {{1012 + loop.index}}
$IP rule add uidrange {{1012 + loop.index}}-{{1012 + loop.index}} lookup {{1012 + loop.index}} priority 1000
$IP rule add from {{net.ip}} lookup {{1012 + loop.index}} priority 1001
{% endfor %}
EOF
{% endblock %}
