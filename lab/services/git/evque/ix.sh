{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/gnugrep
bin/go/smee
bin/etcd/ctl
lab/etc/user(user={{evlog_user}})
lab/services/git/evque/runit(srv_dir=evque_{{evlog_user}},srv_user={{evlog_user}})
{% endblock %}
