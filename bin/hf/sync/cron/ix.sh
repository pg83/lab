{% extends '//die/gen.sh' %}

{# Every 10m: hf_sync via gorn worker; uploads minio/cas → huggingface. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/600-hf-sync.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/hf/sync", "--",
        "dedup", "/hf/sync", "--",
        "gorn", "ignite",
        "--root", "hf_sync",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID_CAS",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY_CAS",
        "--env", "HF_TOKEN=$HF_TOKEN",
        "--",
        "/bin/env", "PATH=/bin",
        "hf_sync"
    ]
}
EOF
{% endblock %}
