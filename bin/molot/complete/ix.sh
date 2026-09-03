{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/minio/patched/client
bin/molot/complete/scripts
{% endblock %}
