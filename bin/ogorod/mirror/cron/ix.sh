{% extends '//die/gen.sh' %}

{# One per repo every 10s; ships clone+fetch+push to a gorn worker.
   A bare name is a pg83 repo; owner/name mirrors someone else's. #}

{% set repos = ['molot', 'gorn', 'ix', 'lab', 'samogon', 'ogorod', 'repology/repology-updater', 'repology/repology-rules'] %}

{% block install %}
mkdir -p ${out}/etc/cron

{% for r in repos %}
{% set name = r.split('/')[-1] %}
cat << 'EOF' > ${out}/etc/cron/10-ogorod-mirror-{{name}}.json
{
    "cmd": [
        "etcd_lock", "/lock/ogorod/mirror/{{name}}", "--",
        "dedup", "/ogorod/mirror/v2/{{name}}", "--",
        "gorn", "ignite",
        "--root", "ogorod_mirror",
        "--",
        "/bin/env", "PATH=/bin",
        "ogorod_mirror", "{{r}}"
    ]
}
EOF
{% endfor %}
{% endblock %}
