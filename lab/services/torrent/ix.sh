{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/q/bittorrent/nox
lab/etc/user(user=torrent)
lab/services/torrent/runit(srv_dir=torrent,srv_user=torrent)
{% endblock %}
