{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/mc
lab/etc
set/stalix
bin/kernel/6/7
bin/kernel/6/6
lab/services/etcd
bin/dropbear/runit
bin/kernel/gengrub
lab/services/collector
lab/services/node/exporter
lab/services/autoupdate(user=ix)
{% endblock %}
