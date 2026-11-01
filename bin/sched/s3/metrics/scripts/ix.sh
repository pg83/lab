{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/sched/{{delay}} ${out}/bin

base64 -d << EOF > ${out}/bin/s3_volume_metrics
{% include 'metrics.py/base64' %}
EOF

cat << 'EOF' > ${out}/etc/sched/{{delay}}/s3-volumes.sh
#!/bin/sh
exec timeout -s KILL 20s s3_volume_metrics
EOF

chmod +x ${out}/bin/s3_volume_metrics ${out}/etc/sched/{{delay}}/s3-volumes.sh
{% endblock %}
