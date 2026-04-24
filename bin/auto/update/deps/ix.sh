{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
etc/user
bin/git/unwrap
bin/auto/update/scripts
{% endblock %}
