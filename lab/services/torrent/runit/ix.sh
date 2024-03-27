{% extends '//lab/services/persist/ix.sh' %}

{% set cm = cluster_map | des %}

{% block srv_user_prepare %}
{{super()}}
mkdir -p /big/{{srv_user}}
chown {{srv_user}}:{{srv_user}} /big/{{srv_user}}
{% endblock %}

{% block srv_command %}
cd /home/{{srv_user}}

mkdir -p profiles
rm -rf data
ln -s /big/{{srv_user}} data

export QBT_NO_SPLASH=1

qbittorrent-nox \
    --profile=\${PWD}/profiles \
    --save-path=\${PWD}/data \
    --webui-port={{cm.ports.torrent_webui}}
{% endblock %}
