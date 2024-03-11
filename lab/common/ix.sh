{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/etc
lab/services/etcd
lab/services/collector
lab/services/node/exporter
lab/services/autoupdate(user=ix)

bin/mc
bin/kernel/6/7
bin/kernel/6/6
bin/kernel/gengrub
bin/dropbear/runit

set/stalix/server
{% endblock %}
