{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/rsync
etc/user/nobody
lab/services/rsyncd/share/runit(srv_dir=rsyncd_{{rsyncd_share}},srv_user=nobody)
{% endblock %}
