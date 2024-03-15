{% extends '//etc/services/runit/script/ix.sh' %}

{% block su_command %}
set -xue
export ETCDCTL_ENDPOINTS=localhost:2379
export IFACE=$(ip -o addr show | grep 10.0.0 | head -n1 | awk '{print $2}')
ip addr del 10.0.0.32/24 dev ${IFACE} || true
exec etcdctl lock proxy -- /bin/bash -c 'source <(echo {{self.us_command() | b64e}} | base64 -d)'
{% endblock %}

{% block us_command %}
set -xue
ip addr add 10.0.0.32/24 dev ${IFACE}
exec su -s /bin/bash proxy -c 'source <(echo {{self.pr_command() | b64e}} | base64 -d)'
{% endblock %}

{% block pr_command %}
exec reproxy \
    --listen=10.0.0.32:8080 \
    --static.enabled \
    --static.rule=ix.samokhvalov.xyz,/,http://lab3:8080/
{% endblock %}

{% block srv_command %}
exec /bin/bash -c 'source <(echo {{self.su_command() | b64e}} | base64 -d)'
{% endblock %}
