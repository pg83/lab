{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/gorn
bin/mirror/fetch/event/scripts
{% endblock %}
