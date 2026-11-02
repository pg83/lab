{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/modelscope/scripts
bin/minio/patched/client
{% endblock %}
