{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/reproxy
bin/etcd/ctl
etc/user/nologin(userid=1006,user=proxy)
lab/services/proxy/runit(srv_dir=proxy)
{% endblock %}
