{% extends '//die/gen.sh' %}

{# Parametric mc-gc cron: cron(root=/<absolute-path-inside-bucket>,
   hours=<retention-hours>, period=<seconds>=3600).

   `root` MUST start with '/'  — it's an absolute path inside the
   `minio` mc-alias (bucket + key prefix). Concatenation with the
   alias is therefore stitch-free: minio{{root}} → minio/gorn/ci.

   Emits /etc/cron/<period>-mc-gc-<sanitized-root>.json that takes the
   /lock/mc/gc<root> etcd lock + dedup on /mc/gc<root>, then ships
   `mc_gc minio<root> <hours>` to a gorn worker via ignite (so the
   listing + bulk delete don't run against the scheduler's 10s timeout).

   Each consuming service registers its own cron with its own root +
   retention — they share the script binary (bin/mc/gc/scripts) but the
   etcd keys derive from <root>, so multiple roots don't collide.
#}

{% if not root %}{{ undefined_root_would_nuke_the_whole_bucket }}{% endif %}
{% if not root.startswith('/') %}{{ root_must_be_absolute_starts_with_slash }}{% endif %}
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
        "--env", "S3_ENDPOINT=$S3_ENDPOINT",
        "--env", "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID",
        "--env", "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY",
        "--",
        "/bin/env", "PATH=/bin",
        "mc_gc", "minio{{root}}", "{{hours}}"
    ]
}
EOF
{% endblock %}
