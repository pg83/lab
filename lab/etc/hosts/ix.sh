{% extends '//die/proxy.sh' %}

{% set cm = cluster_map | des %}
{% set hm = cm.by_host[hostname] %}

{% block install %}
mkdir -p ${out}/etc/hosts.d

cat << EOF > ${out}/etc/hosts.d/01-locals
{{hm.net[1].ip}} minio
{% for x in cm.hosts %}
{{x.ip}} {{x.hostname}}
{{x.nebula.ip}} {{x.hostname}}.nebula
{% for h in x.net %}
{{h.ip}} {{x.hostname}}.{{h.if}}
{% endfor %}
{% endfor %}
EOF
{% endblock %}
