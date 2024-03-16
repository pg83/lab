{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
lab/services/rsyncd/sync(user=mirror,rsync_share=rsync://lab3:{{cm.ports.mirror_rsyncd}}/ix,rsync_where=/home/mirror/data,delay=1000)
{% endblock %}
