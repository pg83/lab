{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
{% if mirror_rsync %}
lab/services/mirror/rsync
{% else %}
lab/services/mirror/fetch
lab/services/rsyncd/share(rsyncd_port={{cm.ports.mirror_rsyncd}},rsyncd_share=ix,rsyncd_path=/home/mirror/data)
{% endif %}
lab/services/serve(serve_from=/home/mirror/data,serve_port={{cm.ports.mirror_http}},serve_user=nobody)
{% endblock %}
