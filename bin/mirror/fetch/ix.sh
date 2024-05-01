{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/cas
bin/make
bin/python
bin/mirror/fetch/scripts
{% endblock %}
