{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/subreaper
bin/git/unwrap
bin/clone/scripts
{% endblock %}
