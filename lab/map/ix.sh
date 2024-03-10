{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/common
lab/hosts/{{hostname}}
{% endblock %}
