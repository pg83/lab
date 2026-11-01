{% extends '//die/gen.sh' %}

{# One daily stable promotion. The long build runs in gorn; schedule and
   work locks are separate, and neither serializes updater/fixer work. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/86400-updater-merger.json
{
    "cmd": [
        "etcd_lock", "/lock/updater/merger/schedule", "--",
        "dedup", "/updater/merger/v1", "--",
        "gorn", "ignite",
        "--root", "updater_merger",
        "--descr", "IX stable merge",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID_MOLOT",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY_MOLOT",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS",
        "--env", "GIT_USER=pg83",
        "--env", "MOLOT_QUIET=1",
        "--",
        "/bin/env", "PATH=/bin",
        "etcd_lock", "/lock/updater/merger/work", "--",
        "updater_merger", "run"
    ]
}
EOF
{% endblock %}
