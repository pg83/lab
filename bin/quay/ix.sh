{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/oras
bin/quay/scripts
bin/minio/patched/client
{% endblock %}
