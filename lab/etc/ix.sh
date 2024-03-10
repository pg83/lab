{% extends '//die/proxy.sh' %}

{% block cluster_map %}
{{cluster_map | b64d}}
{% endblock %}

{% block install %}
mkdir -p ${out}/etc/hosts.d

cat << EOF > ${out}/etc/hosts.d/01-locals
{% for x in (self.cluster_map() | jl) %}
{{x["ip"]}} {{x["hostname"]}}
{% endfor %}
EOF
{% endblock %}
