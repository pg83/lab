{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/cas
bin/make
bin/python
bin/mirror/fetch/scripts
bin/minio/patched/client
{% endblock %}
