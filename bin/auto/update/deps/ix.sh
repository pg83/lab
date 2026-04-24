{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
etc/lab/user
bin/git/unwrap
bin/auto/update/scripts
{% endblock %}
