{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/sched/{{delay}}

base64 -d << EOF > ${out}/etc/sched/{{delay}}/df.sh
{% include 'df.sh/base64' %}
EOF

chmod +x ${out}/etc/sched/{{delay}}/df.sh
{% endblock %}
