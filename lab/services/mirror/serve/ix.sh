{% extends '//die/hub.sh' %}

{% block run_deps %}
etc/user/nobody
lab/services/mirror/serve/bin(from={{serve_from}})
etc/services/runit(srv_dir={{'mirror_serve_' + port}},srv_user=nobody,srv_command=exec serve_ix_mirror)
{% endblock %}
