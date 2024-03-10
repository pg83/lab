{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/etcd/server
lab/services/etcd/scripts
etc/user/nologin(userid=1002,user=etcd)
etc/services/runit(srv_dir=etcd,srv_user=etcd,srv_command=exec etcd_runner)
{% endblock %}
