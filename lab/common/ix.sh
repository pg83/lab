{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/etc

{% if hostname in (cluster_map | des).etcd %}
lab/services/etcd
lab/services/proxy
{% endif %}

lab/services/collector
lab/services/node/exporter
lab/services/autoupdate(user=ix)

bin/mc
bin/htop
bin/kernel/6/7
bin/kernel/6/6
bin/kernel/gengrub
bin/dropbear/runit

set/stalix/server
{% endblock %}
