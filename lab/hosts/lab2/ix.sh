{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/torrent
lab/services/mirror(mirror_rsync=1)
{% endblock %}
