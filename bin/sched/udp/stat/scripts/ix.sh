{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/sched/{{delay}}

base64 -d << EOF > ${out}/etc/sched/{{delay}}/udpstat.sh
{% include 'udpstat.sh/base64' %}
EOF

chmod +x ${out}/etc/sched/{{delay}}/udpstat.sh
{% endblock %}
