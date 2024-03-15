{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/etc

{% if hostname in (cluster_map | des).etcd %}
lab/services/etcd
lab/services/proxy(proxy_ip=10.0.0.32,proxy_port=8080)
#lab/services/proxy(proxy_ip=10.0.0.33,proxy_port=8090,proxy_https=1)
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
