{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/git/unwrap
bin/clone/scripts
{% endblock %}
