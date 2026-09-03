{% extends '//die/gen.sh' %}

{# Keep replies sourced from secondary NICs on the matching interface. #}

{% set cm = cluster_map | des %}
{% set hm = cm.by_host[hostname] %}

{% block install %}
mkdir -p ${out}/etc/runit/1.d

cat << 'EOF' > ${out}/etc/runit/1.d/30-multihome.sh
IP=/ix/realm/ip/bin/ip

{% for net in hm.net if net.if != 'eth0' %}
$IP route replace 10.0.0.0/24 dev {{net.if}} src {{net.ip}} table {{1012 + loop.index}}
$IP rule add from {{net.ip}} lookup {{1012 + loop.index}} priority 1001
{% endfor %}
EOF
{% endblock %}
