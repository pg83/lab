{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/sched/{{delay}}

base64 -d << EOF > ${out}/etc/sched/{{delay}}/ipdiag.sh
{% include 'ipdiag.sh/base64' %}
EOF

chmod +x ${out}/etc/sched/{{delay}}/ipdiag.sh
{% endblock %}
