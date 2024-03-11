{% extends '//die/proxy.sh' %}

{% block install %}
mkdir -p ${out}/etc/hosts.d

cat << EOF > ${out}/etc/hosts.d/01-locals
{% for x in (cluster_map | des).hosts %}
{{x.ip}} {{x.hostname}}
{% endfor %}
EOF
{% endblock %}
