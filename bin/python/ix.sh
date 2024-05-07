{% extends '//die/hub.sh' %}

{% block run_deps %}
{% if hostname == 'lab3' %}
bld/python/frozen(python_ver=12)
{% else %}
bin/python/12
{% endif %}
{% endblock %}
