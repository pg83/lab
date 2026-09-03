{% extends '//die/gen.sh' %}

{# The scheduler only deduplicates and enqueues; scan+PUT run in gorn. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/15-molot-complete.json
{
    "cmd": [
        "etcd_lock", "/lock/molot/complete/schedule", "--",
        "dedup", "/molot/complete/v1", "--",
        "gorn", "ignite",
        "--root", "molot_complete",
        "--descr", "rebuild molot complete index",
        "--env", "MC_HOST_minio=$MC_HOST_minio_molot",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS",
        "--",
        "/bin/env", "PATH=/bin",
        "etcd_lock", "/lock/molot/complete/work", "--",
        "molot_complete"
    ]
}
EOF
{% endblock %}
