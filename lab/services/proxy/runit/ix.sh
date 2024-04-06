{% extends '//etc/services/runit/script/ix.sh' %}

{% set cm = cluster_map | des %}

{% block su_command %}
set -xue
mkdir -p /home/proxy/{{proxy_port}}
chown proxy /home/proxy /home/proxy/{{proxy_port}}
cd /home/proxy/{{proxy_port}}/
etcdctl get htpasswd | tail -n 1 > htpasswd
export IFACE=$(ip -o addr show | grep 10.0.0 | head -n1 | awk '{print $2}')
ip addr del {{proxy_ip}} dev ${IFACE} || true
exec etcdctl lock proxy_{{proxy_port}} -- /bin/sh ${1}/us_command ${1}
{% endblock %}

{% block us_command %}
set -xue
ip addr add {{proxy_ip}}/24 dev ${IFACE}
exec su -s /bin/sh proxy ${1}/pr_command ${1}
{% endblock %}

{% block pr_command %}
exec reproxy \
    --listen={{proxy_ip}}:{{proxy_port}} \
    --static.enabled \
{% if proxy_https %}
    --basic-htpasswd=htpasswd \
    --ssl.type=auto \
    --ssl.http-port=8100 \
 {% for n in cm.by_host.lab2.net %}
    --static.rule=torrents.homelab.cam,/,http://{{n.ip}}:{{cm.ports.torrent_webui}}/ \
 {% endfor %}
{% else %}
 {% for h in ['lab1', 'lab2', 'lab3'] %}
  {% for n in cm.by_host[h].net %}
    --static.rule=ix.homelab.cam,/,http://{{n.ip}}:{{cm.ports.mirror_http}}/ \
  {% endfor %}
 {% endfor %}
 {% for h in ['lab1', 'lab2', 'lab3'] %}
  {% for n in cm.by_host[h].net %}
    --static.rule=webhook.homelab.cam,/,http://{{n.ip}}:{{cm.ports.webhook}}/ \
  {% endfor %}
 {% endfor %}
{% endif %}
    --logger.enabled \
    --logger.stdout
{% endblock %}

{% block srv_command %}
exec /bin/sh ${PWD}/su_command ${PWD}
{% endblock %}

{% block install %}
{{super()}}

base64 -d << EOF > su_command
{{self.su_command() | b64e}}
EOF

base64 -d << EOF > pr_command
{{self.pr_command() | b64e}}
EOF

base64 -d << EOF > us_command
{{self.us_command() | b64e}}
EOF
{% endblock %}
