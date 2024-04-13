{% extends '//die/proxy.sh' %}

{% set cm = cluster_map | des %}

{% block install %}
mkdir -p ${out}/etc/hosts.d

cat << EOF > ${out}/etc/hosts.d/01-locals
{% for x in cm.hosts %}
{{x.ip}} {{x.hostname}}
{% for h in x.net %}
{{h.ip}} {{h.if}}.{{x.hostname}}
{{h.ip}} {{x.hostname}}.{{h.if}}.min
{% endfor %}
{% endfor %}
EOF
{% endblock %}
