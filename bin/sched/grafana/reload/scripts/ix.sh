{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/sched/{{delay}}

cat << 'EOF' > ${out}/etc/sched/{{delay}}/grafana-reload.sh
#!/bin/sh
# Re-scan provisioning without a service restart.
for what in dashboards datasources; do
    curl -fsS --max-time 10 \
        -X POST \
        http://admin:{{password}}@localhost:{{port}}/api/admin/provisioning/${what}/reload \
        -o /dev/null || true
done
EOF

chmod +x ${out}/etc/sched/{{delay}}/grafana-reload.sh
{% endblock %}
