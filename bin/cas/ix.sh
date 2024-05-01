{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/cas/scripts
bin/minio/patched/client
{% endblock %}
