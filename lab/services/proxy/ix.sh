{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/bash
bin/reproxy
bin/etcd/ctl
lab/etc/user(user=proxy)
lab/services/proxy/runit(srv_dir=proxy_{{proxy_port}})
{% endblock %}
