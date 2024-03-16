{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
lab/etc/user
bin/git/unwrap
bin/sched/purge(delay=100,trash_dir={{wd}}/ix_root/trash)
lab/services/ci/runit(srv_dir={{user}},srv_user={{user}})
{% endblock %}
