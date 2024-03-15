{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
lab/services/mirror/unwrap(user=mirror,wd=/home/mirror/,port={{cm.ports.mirror_http}})
{% endblock %}
