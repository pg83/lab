{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/sched/{{delay}}

cat << 'EOF' > ${out}/etc/sched/{{delay}}/grafana-reload.sh
#!/bin/sh
# Grafana reads provisioning/*.yaml only at startup. Explicit
# reload against each provisioning subsystem makes it re-scan
# without a service restart. Datasources, dashboards,
# notifications, plugins, and alerting all have their own
# reload endpoints — we hit dashboards + datasources since
# those are the ones we actually ship.
for what in dashboards datasources; do
    curl -fsS --max-time 10 \
        -X POST \
        http://admin:{{password}}@localhost:{{port}}/api/admin/provisioning/${what}/reload \
        -o /dev/null || true
done
EOF

chmod +x ${out}/etc/sched/{{delay}}/grafana-reload.sh
{% endblock %}
