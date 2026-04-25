{% extends '//die/gen.sh' %}

{# Every 15 min: take the cluster lock so only one host syncs at a
   time, then run ogorod_mirror in-process (no gorn ignite — the
   work is small and the script is on the scheduler's PATH). #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/900-ogorod-mirror.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/ogorod/mirror", "--",
        "ogorod_mirror"
    ]
}
EOF
{% endblock %}
