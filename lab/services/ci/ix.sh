{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/gnugrep
bin/su/exec
bin/etcd/ctl
bin/git/clone
lab/services/ci/scripts
bin/sched/purge(delay=100,trash_dir={{wd}}/ix_root/trash)
{% endblock %}
