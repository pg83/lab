{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/etc/user(user={{serve_user}})
lab/services/serve/bin(from={{serve_from}})
etc/services/runit(srv_dir={{'serve_' + port}},srv_user={{serve_user}},srv_command=exec serve_ix_mirror)
{% endblock %}
