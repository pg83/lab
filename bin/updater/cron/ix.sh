{% extends '//die/gen.sh' %}

{# The scheduler only serializes and enqueues. The long work runs in gorn. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/3600-updater.json
{
    "cmd": [
        "etcd_lock", "/lock/updater", "--",
        "dedup", "/updater/v1", "--",
        "gorn", "ignite",
        "--root", "updater",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID_CIX",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY_CIX",
        "--env", "AWS_ACCESS_KEY_ID_MOLOT=$AWS_ACCESS_KEY_ID_MOLOT",
        "--env", "AWS_SECRET_ACCESS_KEY_MOLOT=$AWS_SECRET_ACCESS_KEY_MOLOT",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS",
        "--env", "GIT_USER=pg83",
        "--env", "GIT_PASS=$GITHUB_TOKEN",
        "--env", "MOLOT_QUIET=1",
        "--env", "MOLOT_FULL_SLOTS=10",
        "--",
        "/bin/env", "PATH=/bin",
        "etcd_lock", "/lock/updater/work", "--",
        "updater", "run"
    ]
}
EOF
{% endblock %}
