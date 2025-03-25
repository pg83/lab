{% extends '//die/hub.sh' %}

{% block run_deps %}
set/fs
bin/rsync
bin/mk/scripts
{% endblock %}
