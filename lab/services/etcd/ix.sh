{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/etcd/server
lab/etc/user(user=etcd)
lab/services/etcd/runit(srv_dir=etcd,srv_user=etcd)
{% endblock %}
