{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python/frozen(python_ver=12,py_extra_modules=pip/requests)
lab/common
lab/hosts/{{hostname}}
{% endblock %}
