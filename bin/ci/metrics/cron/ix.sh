{% extends '//die/gen.sh' %}

{# Single cron entry, fires every 30s. The scanner is incremental
   (etcd cursor on result.json mtime), so a tick processes only
   tasks finished since last run — typically 1-3 across all CI
   tiers. Per the lab convention, real work runs in a gorn worker
   via ignite; the scanner posts directly to the local Loki push
   endpoint from inside the worker. #}

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
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS",
        "--",
        "/bin/env", "PATH=/bin",
        "ci_metrics"
    ]
}
EOF
{% endblock %}
