{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/torrent
lab/services/mirror(mirror_rsync=1)
#lab/services/ci(ci_targets=set/ci/tier/1)
lab/services/sftp(sftp_dir=/home/torrent/profiles/qBittorrent/downloads)
{% endblock %}
