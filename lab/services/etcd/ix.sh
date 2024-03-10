{% extends '//die/hub.sh' %}

{% block etcd_conf %}
--name {{hostname}}
--initial-advertise-peer-urls http://10.0.1.10:2380
--listen-peer-urls http://10.0.1.10:2380
--listen-client-urls http://10.0.1.10:2379,http://127.0.0.1:2379
--advertise-client-urls http://10.0.1.10:2379
--initial-cluster-token etcd-cluster-1
--initial-cluster infra0=http://10.0.1.10:2380,infra1=http://10.0.1.11:2380,infra2=http://10.0.1.12:2380 \
--initial-cluster-state new
{% endblock %}

{% block run_deps %}
bin/etcd/server
etc/user/nologin(userid=1002,user=etcd)
etc/services/runit(srv_dir=etcd,srv_user=etcd,srv_command=exec etcd_runner)
{% endblock %}
