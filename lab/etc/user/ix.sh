{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
{% if user in cm.users %}
etc/user/nologin(userid={{cm.users[user]}})
{% else %}
etc/user/{{user or error()}}
{% endif %}
{% endblock %}
