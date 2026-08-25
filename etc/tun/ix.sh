{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/runit/1.d

cat << EOF > ${out}/etc/runit/1.d/01-03-tun-permissions.sh
# allow unprivileged network namespaces to open the TUN device
chmod 0666 /dev/net/tun
EOF
{% endblock %}
