{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/collector/unwrap(user=collector)
{% endblock %}
