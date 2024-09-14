{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/autoupdate/deps
etc/services/runit(srv_deps=lab/services/autoupdate/deps,srv_dir=autoupdate_{{user}},srv_user={{user}},srv_command=exec autoupdate_cycle)
{% endblock %}
