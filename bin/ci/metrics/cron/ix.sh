{% extends '//die/gen.sh' %}

{# 30s incremental scanner; etcd cursor on result.json mtime. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/30-ci-metrics.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/ci/metrics", "--",
        "dedup", "/ci/metrics", "--",
        "gorn", "ignite",
        "--root", "ci_metrics",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID_GORN",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY_GORN",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS",
        "--",
        "/bin/env", "PATH=/bin",
        "ci_metrics"
    ]
}
EOF
{% endblock %}
