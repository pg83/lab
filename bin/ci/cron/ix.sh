{% extends '//die/gen.sh' %}

{# One cron file per tier; dedup blocks stacking on in-flight runs. #}

{% set tiers = ['set/ci/tier/0', 'set/ci/tier/1', 'set/ci/tier/2'] %}

{% block install %}
mkdir -p ${out}/etc/cron

{% for t in tiers %}
{% set slug = t.replace('/', '_') %}
cat << 'EOF' > ${out}/etc/cron/10-ci-{{slug}}.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/ci/{{slug}}", "--",
        "dedup", "/ci/{{slug}}", "--",
        "gorn", "ignite",
        "--root", "ci",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID_GORN",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY_GORN",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS",
        "--env", "MOLOT_QUIET=1",
        "--env", "MOLOT_FULL_SLOTS=10",
        "--",
        "/bin/env", "PATH=/bin",
        "ci", "check", "{{t}}"
    ]
}
EOF
{% endfor %}
{% endblock %}
