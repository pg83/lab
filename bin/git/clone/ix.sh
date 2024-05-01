{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/git/unwrap
bin/git/clone/scripts
{% endblock %}
