{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/devlink
lab/hosts/lab1/mount
{% endblock %}
