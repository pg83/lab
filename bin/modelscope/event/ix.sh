{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/gorn
bin/python
bin/modelscope/event/scripts
{% endblock %}
