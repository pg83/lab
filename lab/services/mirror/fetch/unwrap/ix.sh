{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/etc/user
lab/services/mirror/fetch/scripts
etc/services/runit(srv_dir=mirror_fetch,srv_user={{user}},srv_command=exec fetch_ix_mirror)
{% endblock %}
