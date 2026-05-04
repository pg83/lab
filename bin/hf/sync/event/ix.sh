{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/gorn
bin/hf/sync/event/scripts
{% endblock %}
