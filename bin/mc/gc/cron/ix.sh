{% extends '//die/gen.sh' %}

{# Parametric mc-gc cron: root MUST be absolute under minio bucket. #}
{# Hard-fail at render so we never emit a cron that mc-rm's a whole bucket. #}

{% set root = root | defined('mc_gc cron: root must be set') %}
{% if not root %}{{ mc_gc_root_empty | defined('mc_gc cron: root must be non-empty') }}{% endif %}
{% if not root.startswith('/') %}{{ mc_gc_root_not_absolute | defined('mc_gc cron: root must start with /') }}{% endif %}
{% set period = period | default('3600') %}
{% set hours = hours | default('1') %}
{% set safe_root = root.lstrip('/') | replace('/', '-') %}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/{{period}}-mc-gc-{{safe_root}}.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/mc/gc{{root}}", "--",
        "dedup", "/mc/gc{{root}}", "--",
        "gorn", "ignite",
        "--root", "mc_gc",
        "--env", "MC_HOST_minio=$MC_HOST_minio",
        "--",
        "/bin/env", "PATH=/bin",
        "minio-client", "rm", "--recursive", "--force", "--bypass", "--older-than={{hours}}h", "minio{{root}}"
    ]
}
EOF
{% endblock %}
