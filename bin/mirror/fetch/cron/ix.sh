{% extends '//die/gen.sh' %}

{# Every 100s: cache_ix_sources via gorn worker; small batched fetches. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/100-mirror-fetch.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/mirror/fetch", "--",
        "dedup", "/mirror/fetch", "--",
        "gorn", "ignite",
        "--root", "mirror_fetch",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "MC_HOST_mirror=$MC_HOST_minio_mirror",
        "--env", "MC_HOST_minio=$MC_HOST_minio_cas",
        "--",
        "/bin/env", "PATH=/bin",
        "cache_ix_sources"
    ]
}
EOF
{% endblock %}
