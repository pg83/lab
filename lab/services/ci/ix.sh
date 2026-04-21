{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/gorn
bin/molot
bin/python
bin/devlink
bin/gnugrep
bin/su/exec
bin/etcd/ctl
bin/git/clone
lab/services/ci/scripts
{% endblock %}
