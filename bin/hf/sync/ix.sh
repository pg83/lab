{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/hf/sync/client
bin/hf/sync/scripts
bin/minio/patched/client
{% endblock %}
