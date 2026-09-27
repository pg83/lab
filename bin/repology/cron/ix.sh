{% extends '//die/gen.sh' %}

{# One job per repository: fetch and parse in gorn, chunks to s3. The
   aggregate folds them into repology/projects.json for the updater.
   Distros every 4 h, our own dumps and the aggregate hourly. #}

{% set repos = [
    ('14400', 'alpine_edge'),
    ('14400', 'arch'),
    ('14400', 'debian_unstable'),
    ('14400', 'fedora_rawhide'),
    ('14400', 'freebsd'),
    ('14400', 'gnuguix'),
    ('14400', 'homebrew'),
    ('14400', 'macports'),
    ('14400', 'nix_unstable'),
    ('14400', 'opensuse_tumbleweed'),
    ('14400', 'void_x86_64'),
    ('3600', 'stalix'),
    ('3600', 'stalix_dev'),
] %}

{% block install %}
mkdir -p ${out}/etc/cron

{% for delay, repo in repos %}
cat << 'EOF' > ${out}/etc/cron/{{delay}}-repology-{{repo}}.json
{
    "cmd": [
        "etcd_lock", "/lock/repology/{{repo}}/schedule", "--",
        "dedup", "/repology/{{repo}}/v1", "--",
        "gorn", "ignite",
        "--root", "repology",
        "--descr", "repology fetch {{repo}}",
        "--env", "MC_HOST_minio=$MC_HOST_minio_repology",
        "--env", "REPOLOGY_SOCKS5=$SOCKS5_PROXY",
        "--",
        "/bin/env", "PATH=/bin",
        "etcd_lock", "/lock/repology/{{repo}}/work", "--",
        "repology", "fetch", "{{repo}}"
    ]
}
EOF
{% endfor %}

cat << 'EOF' > ${out}/etc/cron/3600-repology-aggregate.json
{
    "cmd": [
        "etcd_lock", "/lock/repology/aggregate/schedule", "--",
        "dedup", "/repology/aggregate/v1", "--",
        "gorn", "ignite",
        "--root", "repology",
        "--descr", "repology aggregate",
        "--env", "MC_HOST_minio=$MC_HOST_minio_repology",
        "--",
        "/bin/env", "PATH=/bin",
        "etcd_lock", "/lock/repology/aggregate/work", "--",
        "repology", "aggregate"
    ]
}
EOF
{% endblock %}
