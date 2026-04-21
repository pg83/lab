{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/sched/{{delay}}

cat << 'EOF' > ${out}/etc/sched/{{delay}}/grafana-reload.sh
#!/bin/sh
# Grafana reads provisioning/*.yaml only at startup, and newer
# Grafana (unified storage) sometimes misses new dashboard JSON
# files added to the provider path. Explicit reload forces a
# full rescan without restarting the service.
curl -fsS --max-time 10 \
    -X POST \
    http://admin:admin@localhost:{{port}}/api/admin/provisioning/dashboards/reload \
    -o /dev/null || true
EOF

chmod +x ${out}/etc/sched/{{delay}}/grafana-reload.sh
{% endblock %}
