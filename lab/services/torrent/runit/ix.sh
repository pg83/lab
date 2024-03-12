{% extends '//lab/services/persist/ix.sh' %}

{% block srv_command %}
cd /home/{{srv_user}}

mkdir -p profiles
mkdir -p data

export QBT_NO_SPLASH=1

qbittorrent-nox \
    --profile=${PWD}/profiles \
    --save-path=${PWD}/data \
    --webui-port=8000
{% endblock %}
