{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
lab/common
lab/hosts/{{hostname}}
{% endblock %}
