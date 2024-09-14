{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/gnugrep
lab/etc/user
bin/etcd/ctl
bin/git/clone
lab/services/autoupdate/scripts
{% endblock %}
