{% extends '//etc/services/runit/script/ix.sh' %}

{% set cm = cluster_map | des %}

{% block su_command %}
set -xue
mkdir -p /home/proxy/{{proxy_port}}
chown proxy /home/proxy /home/proxy/{{proxy_port}}
cd /home/proxy/{{proxy_port}}/
export ETCDCTL_ENDPOINTS=localhost:{{cm.etcd.ports.client}}
etcdctl get htpasswd | tail -n 1 > htpasswd
export IFACE=$(ip -o addr show | grep 10.0.0 | head -n1 | awk '{print $2}')
ip addr del {{proxy_ip}} dev ${IFACE} || true
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
    --static.enabled \
    --logger.enabled \
    --logger.stdout \
{% if proxy_https %}
    --basic-htpasswd=htpasswd \
    --ssl.type=auto \
    --ssl.http-port=8100 \
    --static.rule=torrents.homelab.cam,/,http://lab3:8000/
{% else %}
    --static.rule=ix.samokhvalov.xyz,/,http://lab3:8080/ \
    --static.rule=ix.homelab.cam,/,http://lab3:8080/
{% endif %}
{% endblock %}

{% block srv_command %}
exec /bin/bash -c 'source <(echo {{self.su_command() | b64e}} | base64 -d)'
{% endblock %}
