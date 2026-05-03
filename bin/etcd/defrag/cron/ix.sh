{% extends '//die/gen.sh' %}

{# Every hour: under /lock/etcd/defrag, dedup on /etcd/defrag (skip
   if the previous defrag is still queued), fire etcd_defrag on a
   gorn worker. The script walks ETCDCTL_ENDPOINTS and defrags each
   sequentially — one gorn task per cluster, not per host. Lock +
   dedup is the same wrapper every other cron uses (ci, hf, ghcr,
   etcd-backup) and is what keeps the GET+PUT inside dedup atomic
   against fire-on-leader-switchover races. #}

{% block install %}
mkdir -p ${out}/etc/cron

cat << 'EOF' > ${out}/etc/cron/3600-etcd-defrag.json
{
    "cmd": [
        "etcdctl", "lock", "/lock/etcd/defrag", "--",
        "dedup", "/etcd/defrag", "--",
        "gorn", "ignite",
        "--root", "etcd_defrag",
        "--env", "GORN_API=$GORN_API",
        "--env", "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS_PERSIST",
        "--",
        "/bin/env", "PATH=/bin",
        "etcd_defrag"
    ]
}
EOF
{% endblock %}
