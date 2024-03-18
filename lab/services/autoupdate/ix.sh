{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/bash
bin/clone
bin/python
lab/etc/user
lab/services/autoupdate/scripts
etc/services/runit(srv_dir=autoupdate_{{user}},srv_user={{user}},srv_command=exec autoupdate_cycle)
{% endblock %}
