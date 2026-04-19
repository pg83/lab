{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/btrfs/progs
lab/etc/user(user=torrent)
{% endblock %}
