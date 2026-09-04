{% extends '//die/gen.sh' %}

{# The scheduler only deduplicates and enqueues; chunk folding runs in gorn. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/3600-molot-stats.json
{
    "cmd": [
        "etcd_lock", "/lock/molot/stats/schedule", "--",
        "dedup", "/molot/stats/v1", "--",
        "gorn", "ignite",
        "--root", "molot_stats",
        "--descr", "fold molot cache usage stats",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "S3_BUCKET=molot",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID_MOLOT",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY_MOLOT",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS",
        "--",
        "/bin/env", "PATH=/bin",
        "etcd_lock", "/lock/molot/stats/work", "--",
        "molot", "stats"
    ]
}
EOF
{% endblock %}
