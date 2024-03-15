{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/reproxy
bin/etcd/ctl
lab/services/proxy/runit(srv_dir=proxy)
etc/user/nologin(userid=1006,user=proxy)
{% endblock %}
