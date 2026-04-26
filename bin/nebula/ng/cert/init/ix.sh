{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/etcd/ctl
bin/nebula/ng/cert
bin/nebula/ng/cert/init/scripts
{% endblock %}
