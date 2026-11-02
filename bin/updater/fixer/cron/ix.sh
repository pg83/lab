{% extends '//die/gen.sh' %}

{#
The scheduler only performs the short enqueue.  dedup keeps one fixer task in
gorn, while /lock/updater/fixer/work excludes only another fixer.  The
mechanical updater has its own lock and may run in parallel.
#}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/300-updater-fixer.json
{
    "cmd": [
        "etcd_lock", "/lock/updater/fixer/schedule", "--",
        "dedup", "/updater/fixer/v6", "--",
        "gorn", "ignite",
        "--root", "updater_fixer",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID_MOLOT",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY_MOLOT",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS",
        "--env", "ETCD_PERSIST_ENDPOINTS=$ETCD_PERSIST_ENDPOINTS",
        "--env", "GIT_USER=pg83",
        "--env", "IX_FIXER_KIMI_GORN_API=$KIMI_GORN_API",
        "--env", "IX_FIXER_KIMI_S3_ENDPOINT=$KIMI_S3_ENDPOINT",
        "--env", "IX_FIXER_KIMI_MOLOT_RESOLVE=$KIMI_MOLOT_RESOLVE",
        "--env", "IX_FIXER_GENERATION=9",
        "--env", "MOLOT_QUIET=1",
        "--",
        "/bin/env", "PATH=/bin",
        "etcd_lock", "/lock/updater/fixer/work", "--",
        "updater_fixer", "run"
    ]
}
EOF
{% endblock %}
