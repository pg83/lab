{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/sched/{{delay}}
mkdir -p ${out}/bin

base64 -d << EOF > ${out}/bin/smart_metrics
{% include 'smart.py/base64' %}
EOF

chmod +x ${out}/bin/smart_metrics

base64 -d << EOF > ${out}/etc/sched/{{delay}}/smart.sh
{% include 'smart.sh/base64' %}
EOF

chmod +x ${out}/etc/sched/{{delay}}/smart.sh
{% endblock %}
