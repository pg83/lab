{% extends '//die/proxy.sh' %}

{% block install %}
mkdir -p ${out}/etc/runit/1.d
cat << EOF > ${out}/etc/runit/1.d/20-mount-rw.sh
{% block mount %}
{% endblock %}
EOF
{% endblock %}
