{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/btrfs/progs
lab/hosts/lab2/mount
lab/etc/user(user=torrent)
{% endblock %}
