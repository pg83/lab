{% extends '//die/gen.sh' %}

{# Hourly etcd_backup via gorn worker; Tower-of-Hanoi slots in MinIO. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/3600-etcd-backup.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/backup/etcd", "--",
        "dedup", "/backup/etcd", "--",
        "gorn", "ignite",
        "--root", "backup",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID_GORN",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY_GORN",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS_PERSIST",
        "--",
        "/bin/env", "PATH=/bin",
        "etcd_backup"
    ]
}
EOF
{% endblock %}
