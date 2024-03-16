{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
lab/services/mirror
lab/services/torrent
lab/services/sftp(sftp_dir=/home/torrent/profiles/qBittorrent/downloads)
lab/services/rsyncd/share(rsyncd_port={{cm.ports.mirror_rsyncd}},rsyncd_share=ix,rsyncd_path=/home/mirror/data)
{% endblock %}
