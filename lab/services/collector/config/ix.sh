{% extends '//die/proxy.sh' %}

{% block install %}
mkdir ${out}/etc

cat << EOF > ${out}/etc/prometheus.conf
{% include 'prometheus.conf' %}
EOF
{% endblock %}
