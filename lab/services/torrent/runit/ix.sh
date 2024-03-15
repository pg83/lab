{% extends '//lab/services/persist/ix.sh' %}

{% set cm = cluster_map | des %}

{% block srv_command %}
cd /home/{{srv_user}}

mkdir -p profiles
mkdir -p data

export QBT_NO_SPLASH=1

qbittorrent-nox \
    --profile=\${PWD}/profiles \
    --save-path=\${PWD}/data \
    --webui-port={{cm.ports.torrent_webui}}
{% endblock %}
