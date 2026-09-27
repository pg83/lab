{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/sched/{{delay}} ${out}/share/s3-scan

base64 -d << EOF > ${out}/share/s3-scan/config.json
{{s3_config}}
EOF

cat << 'EOF' > ${out}/etc/sched/{{delay}}/s3-scan.sh
#!/bin/sh
exec s3 scan -c /ix/realm/system/share/s3-scan/config.json -host {{s3_host}}
EOF

chmod +x ${out}/etc/sched/{{delay}}/s3-scan.sh
{% endblock %}
