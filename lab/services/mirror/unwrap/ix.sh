{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/wget
bin/make
bin/python
lab/etc/user
bin/git/unwrap
etc/user/nobody
lab/services/mirror/fetch
lab/services/mirror/serve(from={{wd + '/data'}})
etc/services/runit(srv_dir={{'mirror_serve_' + port}},srv_user=nobody,srv_command=exec serve_ix_mirror)
etc/services/runit(srv_dir={{'mirror_fetch_' + port}},srv_user={{user}},srv_command=exec fetch_ix_mirror {{wd}})
{% endblock %}
