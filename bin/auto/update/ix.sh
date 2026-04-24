{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/auto/update/deps
etc/services/runit(srv_deps=bin/auto/update/deps,srv_dir=autoupdate_{{user}},srv_user={{user}},srv_command=exec autoupdate_cycle)
{% endblock %}
