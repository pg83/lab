{% extends '//die/proxy.sh' %}

{% block install %}
cd ${out}; mkdir -p etc/sched/{{delay}}; cd etc/sched/{{delay}}
cat << EOF > upnpc_{{upnp_ext_port}}_{{upnp_proto}}.sh
upnpc -a {{upnp_ip}} {{upnp_port}} {{upnp_ext_port}} {{upnp_proto}} 200
EOF
{% endblock %}
