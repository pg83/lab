{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/git/unwrap
etc/user/{{user}}
lab/autoupdate/scripts
etc/services/runit(srv_dir=autoupdate_{{user}},srv_user={{user}},srv_command=exec autoupdate_cycle)
{% endblock %}
