{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/openssl
bin/secrets/v2/scripts
{% endblock %}
