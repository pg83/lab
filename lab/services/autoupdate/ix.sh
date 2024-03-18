{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/clone
bin/python
bin/gnugrep
lab/etc/user
bin/etcd/ctl
lab/services/autoupdate/scripts
etc/services/runit(srv_dir=autoupdate_{{user}},srv_user={{user}},srv_command=exec autoupdate_cycle)
{% endblock %}
