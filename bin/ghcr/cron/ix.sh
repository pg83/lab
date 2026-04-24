{% extends '//die/gen.sh' %}

{# Every 10m: take the cluster lock, dedup on /ghcr/sync, fire
   ghcr_sync on a gorn worker. ghcr_sync lists minio/cas, diffs
   against ghcr.io/stal-ix/pkgsrc, pushes anything missing via oras. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/600-ghcr-sync.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/ghcr/sync", "--",
        "dedup", "/ghcr/sync", "--",
        "gorn", "ignite",
        "--root", "ghcr_sync",
        "--retry-error",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY",
        "--env", "GHCR_TOKEN=$GHCR_TOKEN",
        "--",
        "/bin/env", "PATH=/bin",
        "ghcr_sync"
    ]
}
EOF
{% endblock %}
