{% extends '//etc/services/runit/script/ix.sh' %}

{% block srv_user_prepare %}
mkdir -p /home/{{srv_user}}
chown {{srv_user}}:{{srv_user}} /home/{{srv_user}}
{% endblock %}
