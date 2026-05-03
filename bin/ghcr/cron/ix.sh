{% extends '//die/gen.sh' %}

{# Every 10m: ghcr_sync via gorn worker; pushes minio/cas → ghcr.io. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/600-ghcr-sync.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/ghcr/sync", "--",
        "dedup", "/ghcr/sync", "--",
        "gorn", "ignite",
        "--root", "ghcr_sync",
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
