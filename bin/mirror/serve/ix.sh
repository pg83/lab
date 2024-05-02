{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/minio/patched/client
bin/mirror/serve/scripts
{% endblock %}
