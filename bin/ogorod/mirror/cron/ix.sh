{% extends '//die/gen.sh' %}

{# One per repo every 10s; ships clone+fetch+push to a gorn worker. #}

{% set repos = ['molot', 'gorn', 'ix', 'lab', 'samogon', 'ogorod'] %}

{% block install %}
mkdir -p ${out}/etc/cron

{% for r in repos %}
cat << 'EOF' > ${out}/etc/cron/10-ogorod-mirror-{{r}}.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/ogorod/mirror/{{r}}", "--",
        "dedup", "/ogorod/mirror/v2/{{r}}", "--",
        "gorn", "ignite",
        "--root", "ogorod_mirror",
        "--env", "GORN_API=$GORN_API",
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID_CIX=$AWS_ACCESS_KEY_ID_CIX",
        "--env", "AWS_SECRET_ACCESS_KEY_CIX=$AWS_SECRET_ACCESS_KEY_CIX",
        "--env", "ETCDCTL_ENDPOINTS_PERSIST=$ETCDCTL_ENDPOINTS_PERSIST",
        "--",
        "/bin/env", "PATH=/bin",
        "ogorod_mirror", "{{r}}"
    ]
}
EOF
{% endfor %}
{% endblock %}
