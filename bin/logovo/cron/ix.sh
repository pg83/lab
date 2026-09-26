{% extends '//die/gen.sh' %}

{# The scheduler only serializes and enqueues; the work runs in gorn under
   its own lock, so a slow merge never overlaps the next one. #}

{% set jobs = [('60', 'merge'), ('600', 'index')] %}

{% block install %}
mkdir -p ${out}/etc/cron

{% for delay, cmd in jobs %}
cat << 'EOF' > ${out}/etc/cron/{{delay}}-logovo-{{cmd}}.json
{
    "cmd": [
        "etcd_lock", "/lock/logovo/{{cmd}}/schedule", "--",
        "dedup", "/logovo/{{cmd}}/v1", "--",
        "gorn", "ignite",
        "--root", "logovo",
        "--env", "S3_ENDPOINT=$LOGOVO_S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID_LOGOVO",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY_LOGOVO",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS",
        "--",
        "/bin/env", "PATH=/bin",
        "etcd_lock", "/lock/logovo/{{cmd}}/work", "--",
        "logovo", "{{cmd}}", "-store", "s3://logovo"
    ]
}
EOF
{% endfor %}
{% endblock %}
