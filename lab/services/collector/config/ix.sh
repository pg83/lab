{% extends '//die/proxy.sh' %}

{% set cm = cluster_map | des %}

{% block install %}
mkdir ${out}/etc

cat << EOF > ${out}/etc/prometheus.conf
{% include 'prometheus.conf' %}
EOF
{% endblock %}
