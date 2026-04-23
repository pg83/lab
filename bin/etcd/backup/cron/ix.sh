{% extends '//die/gen.sh' %}

{# Every 6h: take the lock, dedup on /backup/etcd (skip if the
   previous snapshot is still queued), fire etcd_backup on a gorn
   worker. The worker-side script lives in bin/etcd/backup/scripts. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/21600-etcd-backup.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/backup/etcd", "--",
        "dedup", "/backup/etcd", "--",
        "gorn", "ignite",
        "--root", "backup",
        "--retry-error",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS",
        "--",
        "/bin/env", "PATH=/bin",
        "etcd_backup"
    ]
}
EOF
{% endblock %}
