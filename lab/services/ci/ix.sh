{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/devlink
bin/gnugrep
bin/su/exec
bin/etcd/ctl
bin/git/clone
lab/services/ci/scripts
{% endblock %}
