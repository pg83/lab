{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/git/unwrap
etc/user/nologin(userid=104)
bin/sched/purge(delay=100,trash_dir={{wd}}/ix_root/trash)
lab/services/ci/runit(srv_dir=ci_cycle_{{user}},srv_user={{user}})
{% endblock %}
