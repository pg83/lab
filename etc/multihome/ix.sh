{% extends '//die/gen.sh' %}

{# Keep replies sourced from any NIC's address on that NIC's wire, for
   on-subnet peers (/24) and for external clients (default) alike. #}

{% set cm = cluster_map | des %}
{% set hm = cm.by_host[hostname] %}

{% block install %}
mkdir -p ${out}/etc/runit/1.d

cat << 'EOF' > ${out}/etc/runit/1.d/30-multihome.sh
{% for net in hm.net %}
ip route replace 10.0.0.0/24 dev {{net.if}} src {{net.ip}} table {{1012 + loop.index0}}
ip route replace default via {{net.gw}} dev {{net.if}} src {{net.ip}} table {{1012 + loop.index0}}
ip rule add from {{net.ip}} lookup {{1012 + loop.index0}} priority 1001
{% endfor %}
EOF
{% endblock %}
