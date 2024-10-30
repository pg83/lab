{% extends '//bin/haproxy/ix.sh' %}

{% block make_flags %}
{{super()}}
USE_CPU_AFFINITY=0
{% endblock %}
