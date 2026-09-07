{% extends '//die/gen.sh' %}

{# One-shot batch setup of the router redirects exposing molot cache:
   ext 8054+N -> every physical NIC's :8054, N = last IP octet - 64.
   Run manually: xapi_molot_cache <router_ip> <router_password>. #}

{% set cm = cluster_map | des %}

{% block install %}
mkdir -p ${out}/bin

cat << 'EOF' > ${out}/bin/xapi_molot_cache
#!/bin/sh
set -ue

if [ $# -ne 2 ]; then
    echo "usage: xapi_molot_cache <router_ip> <router_password>" >&2
    exit 2
fi

{% for hn in ['lab1', 'lab2', 'lab3'] %}
{% for net in cm.by_host[hn].net %}
xapi "$1" "$2" molot_cache_{{hn}}_{{net.if}} 1 {{8054 + (net.ip.split('.')[3] | int) - 64}} {{net.ip}} {{cm.ports.molot_cache}}
{% endfor %}
{% endfor %}
EOF

chmod +x ${out}/bin/xapi_molot_cache
{% endblock %}
