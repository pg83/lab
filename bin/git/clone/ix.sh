{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/git/unwrap
bin/git/clone/scripts
{% endblock %}
