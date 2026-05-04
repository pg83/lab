{% extends '//die/gen.sh' %}

{# Hourly etcd_defrag via gorn worker; one task walks all endpoints. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/3600-etcd-defrag.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/etcd/defrag", "--",
        "dedup", "/etcd/defrag", "--",
        "gorn", "ignite",
        "--root", "etcd_defrag",
        "--env", "GORN_API=$GORN_API",
        "--env", "ETCDCTL_ENDPOINTS=$ETCD_PERSIST_ENDPOINTS",
        "--",
        "/bin/env", "PATH=/bin",
        "etcd_defrag"
    ]
}
EOF
{% endblock %}
