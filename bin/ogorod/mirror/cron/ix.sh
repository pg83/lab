{% extends '//die/gen.sh' %}

{# One cron entry per repo, fired every 10s under
   /lock/ogorod/mirror/<r> + dedup. Real work is shipped to a gorn
   worker so the 10s job_scheduler timeout doesn't kill long
   first-time clones (lab is ~80 MB, ix is ~33 MB packed). The
   worker runs in its own unshared+tmpfs ns — no on-disk state
   between ticks, only the localhost-fast clone-from-ourselves +
   github delta + push-back. #}

{% set repos = ['molot', 'gorn', 'ix', 'lab', 'samogon', 'ogorod'] %}

{% block install %}
mkdir -p ${out}/etc/cron

{% for r in repos %}
cat << 'EOF' > ${out}/etc/cron/10-ogorod-mirror-{{r}}.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/ogorod/mirror/{{r}}", "--",
        "dedup", "/ogorod/mirror/{{r}}", "--",
        "gorn", "ignite",
        "--root", "ogorod_mirror",
        "--retry-error",
        "--",
        "/bin/env", "PATH=/bin",
        "ogorod_mirror", "{{r}}"
    ]
}
EOF
{% endfor %}
{% endblock %}
