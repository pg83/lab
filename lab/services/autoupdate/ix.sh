{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/gnugrep
lab/etc/user
bin/etcd/ctl
bin/git/clone
lab/services/autoupdate/scripts
etc/services/runit(srv_dir=autoupdate_{{user}},srv_user={{user}},srv_command=exec autoupdate_cycle)
{% endblock %}
