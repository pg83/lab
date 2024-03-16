{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/wget
bin/make
bin/python
lab/etc/user
bin/git/unwrap
lab/services/mirror/fetch/scripts
etc/services/runit(srv_dir=mirror_fetch,srv_user={{user}},srv_command=exec fetch_ix_mirror {{wd}})
{% endblock %}
