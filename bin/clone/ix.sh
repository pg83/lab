{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/go/smee
bin/subreaper
bin/git/unwrap
bin/clone/scripts
{% endblock %}
