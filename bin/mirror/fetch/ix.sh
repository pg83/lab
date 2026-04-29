{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/cas
bin/make
bin/python
bin/mirror/fetch/cron
bin/mirror/fetch/scripts
bin/minio/patched/client
bin/mc/gc/cron(root=/gorn/mirror_fetch,hours=1)
{% endblock %}
