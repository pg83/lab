{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/lsblk
bin/python
bin/devlink/scripts
{% endblock %}
