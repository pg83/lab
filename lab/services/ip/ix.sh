{% extends '//die/proxy.sh' %}

{% block install %}
mkdir -p ${out}/etc/runit/1.d

cat << EOF > ${out}/etc/runit/1.d/20-{{ip_iface}}.sh
ip addr add {{ip_addr}} dev {{ip_iface}}
EOF
{% endblock %}
