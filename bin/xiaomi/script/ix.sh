{% extends '//die/proxy.sh' %}

{% block install %}
cd ${out}; mkdir -p etc/sched/{{delay}}; cd etc/sched/{{delay}}
cat << EOF > xiaomi_{{xiaomi_name}}.sh
xapi {{xiaomi_gw}} {{xiaomi_passwd}} {{xiaomi_name}} {{xiaomi_proto}} {{upnp_ext_port}} {{upnp_ip}} {{upnp_port}}
EOF
{% endblock %}
