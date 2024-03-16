{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
etc/user/nologin(userid={{cm.users[user]}})
{% endblock %}
