{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/ix/ci
lab/services/vault
{% endblock %}
