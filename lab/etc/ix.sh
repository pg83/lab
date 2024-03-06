{% extends '//die/proxy.sh' %}

{% block install %}
mkdir -p ${out}/etc/hosts.d

cat << EOF > ${out}/etc/hosts.d/01-locals
10.0.0.85  host1
10.0.0.251 host2
10.0.0.85  lab1
10.0.0.251 lab2
EOF
{% endblock %}
