{% extends '//die/gen.sh' %}

{# Parametric mc-gc cron: cron(root=/<absolute-path-inside-bucket>,
   hours=<retention-hours>, period=<seconds>=3600).

   `root` MUST start with '/' — it's an absolute path inside the
   `minio` mc-alias (bucket + key prefix). Concatenation with the
   alias is therefore stitch-free: minio{{root}} → minio/gorn/ci.

   Emits /etc/cron/<period>-mc-gc-<sanitized-root>.json: take
   /lock/mc/gc<root> + dedup on /mc/gc<root>, then ship the
   `minio-client rm --recursive --force --bypass --older-than=<H>h`
   call to a gorn worker via ignite (so the bulk delete doesn't run
   against the scheduler's 10s timeout). The mc alias is forwarded
   in MC_HOST_minio (JobScheduler bakes it from S3 creds + endpoint).

   Each consuming service registers its own cron with its own root +
   retention; the etcd lock/dedup keys derive from <root>, so multiple
   roots don't collide.
#}

{# Hard fail at render time on bad/missing root so we never emit a
   cron command that mc-rm's a whole bucket. flt_defined raises if
   its input is Undefined; we feed it `root` for the missing-arg
   check and a deliberately-undefined name for the empty / not-
   absolute checks (its message string carries the diagnostic). #}
{% set root = root | defined('mc_gc cron: root must be set') %}
{% if not root %}{{ mc_gc_root_empty | defined('mc_gc cron: root must be non-empty') }}{% endif %}
{% if not root.startswith('/') %}{{ mc_gc_root_not_absolute | defined('mc_gc cron: root must start with /') }}{% endif %}
{% set period = period | default('3600') %}
{% set hours = hours | default('24') %}
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
        "--retry-error",
        "--env", "MC_HOST_minio=$MC_HOST_minio",
        "--",
        "/bin/env", "PATH=/bin",
        "minio-client", "rm", "--recursive", "--force", "--bypass", "--older-than={{hours}}h", "minio{{root}}"
    ]
}
EOF
{% endblock %}
