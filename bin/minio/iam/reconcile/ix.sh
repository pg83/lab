{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/minio/iam/reconcile/scripts
{% endblock %}
