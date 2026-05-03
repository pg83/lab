{% extends '//die/gen.sh' %}

{# Every 1h: take the lock, dedup on /backup/etcd (skip if the
   previous snapshot is still queued), fire etcd_backup on a gorn
   worker. The worker-side script lives in bin/etcd/backup/scripts,
   writing into one of 16 Tower-of-Hanoi slots. #}

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
