{% extends '//die/gen.sh' %}

{# Every 10s: take the cluster lock, dedup so a slow tick can't
   queue behind itself. The script's hot path is six ls-remote
   round-trips and an early-exit on no diff. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/10-ogorod-mirror.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/ogorod/mirror", "--",
        "dedup", "/ogorod/mirror", "--",
        "ogorod_mirror"
    ]
}
EOF
{% endblock %}
