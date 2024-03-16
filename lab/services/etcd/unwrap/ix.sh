{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/etc/user
bin/etcd/server
lab/services/etcd/runit(srv_dir={{user}},srv_user={{user}})
{% endblock %}
