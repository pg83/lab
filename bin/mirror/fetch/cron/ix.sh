{% extends '//die/gen.sh' %}

{# Every 10m: take the cluster lock, dedup on /mirror/fetch, fire
   cache_ix_sources on a gorn worker. Script pulls the manifest of
   already-fetched URL-shas from MinIO, diffs against upstream
   urls.txt, fetches only new ones, and merges back. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/600-mirror-fetch.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/mirror/fetch", "--",
        "dedup", "/mirror/fetch", "--",
        "gorn", "ignite",
        "--root", "mirror_fetch",
        "--retry-error",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY",
        "--",
        "/bin/env", "PATH=/bin",
        "cache_ix_sources"
    ]
}
EOF
{% endblock %}
