{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/go/smee
lab/etc/user(user={{evlog_user}})
lab/services/git/evlog/runit(srv_dir=evlog_{{evlog_user}},srv_user={{evlog_user}})
{% endblock %}
