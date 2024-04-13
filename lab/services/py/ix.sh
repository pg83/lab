{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/su/exec
lab/services/py/runit
{% endblock %}
