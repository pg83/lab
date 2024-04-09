{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/http/serve
lab/etc/user(user={{serve_user}})
etc/services/runit(srv_dir={{'serve_' + serve_port}},srv_user={{serve_user}},srv_command=exec http_serve {{serve_port}} {{serve_from}})
{% endblock %}
