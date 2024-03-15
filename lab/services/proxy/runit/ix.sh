{% extends '//etc/services/runit/script/ix.sh' %}

{% block su_command %}
set -xue
mkdir -p var
chown proxy var
export ETCDCTL_ENDPOINTS=localhost:2379
export IFACE=$(ip -o addr show | grep 10.0.0 | head -n1 | awk '{print $2}')
ip addr del {{proxy_ip}}/24 dev ${IFACE} || true
exec etcdctl lock proxy_{{proxy_port}} -- /bin/bash -c 'source <(echo {{self.us_command() | b64e}} | base64 -d)'
{% endblock %}

{% block us_command %}
set -xue
ip addr add {{proxy_ip}}/24 dev ${IFACE}
exec su -s /bin/bash proxy -c 'source <(echo {{self.pr_command() | b64e}} | base64 -d)'
{% endblock %}

{% block pr_command %}
exec reproxy \
    --listen={{proxy_ip}}:{{proxy_port}} \
    --listen=localhost:{{proxy_port}} \
    --static.enabled \
    --logger.enabled \
    --logger.stdout \
{% if proxy_https %}
    --ssl.type=auto \
    --static.rule=torrents.homelab.cam,/,http://lab3:8000/ \
{% else %}
    --static.rule=torrents.homelab.cam,/,http://localhost:8090/ \
    --static.rule=ix.samokhvalov.xyz,/,http://lab3:8080/ \
    --static.rule=ix.homelab.cam,/,http://lab3:8080/ \
{% endif %}
    --static.rule=a,b,c
{% endblock %}

{% block srv_command %}
exec /bin/bash -c 'source <(echo {{self.su_command() | b64e}} | base64 -d)'
{% endblock %}
