{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/openssl
bin/etcd/ctl
bin/secrets/v2/scripts
{% endblock %}
