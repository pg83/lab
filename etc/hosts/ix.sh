{% extends '//die/gen.sh' %}

{% set cm = cluster_map | des %}

{% block install %}
mkdir -p ${out}/etc/hosts.d

cat << EOF > ${out}/etc/hosts.d/01-locals
{% for x in cm.hosts %}
{{x.ip}} {{x.hostname}}
{{x.gofra.ip}} {{x.gofra.hostname}}
{{x.mesh.ip}} {{x.mesh.hostname}}
{% for h in x.net %}
{{h.ip}} {{x.hostname}}.{{h.if}}
{% endfor %}
{% endfor %}
EOF
{% endblock %}
