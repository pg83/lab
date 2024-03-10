{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/etcd/server
etc/user/nologin(userid=1002,user=etcd)
lab/services/etcd/runit(srv_dir=etcd,srv_user=etcd)
{% endblock %}
