{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/q/bittorrent/nox
etc/user/nologin(userid=1004,user=torrent)
lab/services/torrent/runit(srv_dir=torrent,srv_user=torrent)
{% endblock %}
