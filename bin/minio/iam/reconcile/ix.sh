{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/minio/iam/reconcile/cron
bin/minio/iam/reconcile/scripts
bin/mc/gc/cron(root=/gorn/minio_iam_reconcile,hours=1)
{% endblock %}
