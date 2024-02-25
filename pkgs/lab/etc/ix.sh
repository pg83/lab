{% extends '//die/proxy.sh' %}

{% block install %}
mkdir -p ${out}/etc/hosts.d

cat << EOF > ${out}/etc/hosts.d/01-locals
10.0.0.85 host1
EOF
{% endblock %}
