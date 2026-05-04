{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/gorn
bin/dedup
bin/python
bin/etcd/ctl
bin/ix/timeout
bin/minio/patched/client
bin/job/scheduler/scripts

bin/ghcr/cron
bin/hf/sync/cron
bin/ci/metrics/cron
bin/etcd/backup/cron
bin/etcd/defrag/cron
bin/mirror/fetch/cron
bin/ogorod/mirror/cron
bin/minio/iam/reconcile/cron

bin/mc/gc/cron(root=/gorn/ci,hours=1)
bin/mc/gc/cron(root=/gorn/cli,hours=24)
bin/mc/gc/cron(root=/gorn/mc_gc,hours=1)
bin/mc/gc/cron(root=/gorn/backup,hours=24)
bin/mc/gc/cron(root=/gorn/hf_sync,hours=2)
bin/mc/gc/cron(root=/gorn/samogon,hours=1)
bin/mc/gc/cron(root=/gorn/ghcr_sync,hours=2)
bin/mc/gc/cron(root=/gorn/ci_metrics,hours=1)
bin/mc/gc/cron(root=/gorn/etcd_defrag,hours=24)
bin/mc/gc/cron(root=/gorn/mirror_fetch,hours=1)
bin/mc/gc/cron(root=/gorn/ogorod_mirror,hours=1)
bin/mc/gc/cron(root=/gorn/minio_iam_reconcile,hours=1)
{% endblock %}
