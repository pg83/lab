{% extends '//etc/services/runit/script/ix.sh' %}

{% block su_command %}
set -xue
export ETCDCTL_ENDPOINTS=localhost:2379
export IFACE=$(ip -o addr show | grep 10.0.0 | head -n1 | awk '{print $2}')
ip addr del 10.0.0.32/24 dev ${IFACE} || true
etcdctl lock proxy -- /bin/sh -c 'echo {{self.us_command() | b64e}} | base64 -d | /bin/sh'
{% endblock %}

{% block us_command %}
set -xue
ip addr add 10.0.0.32/24 dev ${IFACE}
cat << EOF | su -s /bin/sh proxy
reproxy --static.enabled
EOF
ip addr del 10.0.0.32/24 dev ${IFACE}
{% endblock %}

{% block srv_command %}
exec /bin/sh -c 'echo {{self.su_command() | b64e}} | base64 -d | /bin/sh'
{% endblock %}
