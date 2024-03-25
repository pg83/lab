{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/btrfs/progs
lab/services/mirror
lab/services/torrent
lab/hosts/lab3/mount
lab/services/sftp(sftp_dir=/home/torrent/profiles/qBittorrent/downloads)
{% endblock %}
