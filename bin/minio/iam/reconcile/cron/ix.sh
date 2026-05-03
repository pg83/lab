{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/300-minio-iam-reconcile.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/minio/iam", "--",
        "dedup", "/minio/iam", "--",
        "gorn", "ignite",
        "--root", "minio_iam_reconcile",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$ROOT_S3_USER",
        "--env", "AWS_SECRET_ACCESS_KEY=$ROOT_S3_PASSWORD",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS_PERSIST",
        "--",
        "/bin/env", "PATH=/bin",
        "minio_iam_reconcile"
    ]
}
EOF
{% endblock %}
