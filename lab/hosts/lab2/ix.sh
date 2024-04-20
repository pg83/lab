{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/etc/user(user=torrent)
bin/btrfs/progs
lab/hosts/lab2/mount
{% endblock %}
