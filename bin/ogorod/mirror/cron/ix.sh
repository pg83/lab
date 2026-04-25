{% extends '//die/gen.sh' %}

{# One cron entry per repo, each on its own /lock/ogorod/mirror/<r>
   so a slow github fetch on one repo can't stall the others, and
   the cluster's three hosts can each be syncing a different repo
   in parallel. #}

{% set repos = ['molot', 'gorn', 'ix', 'lab', 'samogon', 'ogorod'] %}

{% block install %}
mkdir -p ${out}/etc/cron

{% for r in repos %}
cat << 'EOF' > ${out}/etc/cron/10-ogorod-mirror-{{r}}.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/ogorod/mirror/{{r}}", "--",
        "dedup", "/ogorod/mirror/{{r}}", "--",
        "ogorod_mirror", "{{r}}"
    ]
}
EOF
{% endfor %}
{% endblock %}
