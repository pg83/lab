{% extends '//die/hub.sh' %}

{% block run_deps %}
etc/lab/user
bin/port/forwarder/rs
etc/services/runit(srv_dir=pf_{{upnp_ext_port}}_{{upnp_proto}},srv_command=exec pf {{upnp_ip}} {{upnp_proto}}/{{upnp_port}}/{{upnp_ext_port}},srv_user={{user}})
{% endblock %}
