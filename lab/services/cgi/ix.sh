{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/cgi/server
lab/etc/user(user={{cgi_user}})
etc/services/runit(srv_dir=cgi_{{cgi_port}},srv_user={{cgi_user}},srv_command=exec cgi_server 0.0.0.0:{{cgi_port}} {{cgi_dir}})
{% endblock %}
