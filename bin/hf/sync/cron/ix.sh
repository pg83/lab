{% extends '//die/gen.sh' %}

{# Every 10m: take the cluster lock, dedup on /hf/sync, fire hf_sync
   on a gorn worker. hf_sync lists minio/cas, diffs against the
   huggingface pkgsrc repo, uploads anything missing. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/600-hf-sync.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/hf/sync", "--",
        "dedup", "/hf/sync", "--",
        "gorn", "ignite",
        "--root", "hf_sync",
        "--retry-error",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY",
        "--env", "HF_TOKEN=$HF_TOKEN",
        "--",
        "/bin/env", "PATH=/bin",
        "hf_sync"
    ]
}
EOF
{% endblock %}
