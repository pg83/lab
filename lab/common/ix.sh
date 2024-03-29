{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
lab/etc

{% if hostname in cm.etcd.hosts %}
lab/services/etcd
lab/services/proxy(proxy_ip=10.0.0.32,proxy_port={{cm.ports.proxy_http}})
lab/services/proxy(proxy_ip=10.0.0.33,proxy_port={{cm.ports.proxy_https}},proxy_https=1)
{% endif %}

lab/services/collector
lab/services/node/exporter
lab/services/autoupdate(user=ix)

lab/services/hz
lab/services/git/cgi(evlog_topic=git_ci)
lab/services/git/cgi(evlog_topic=git_lab)

bin/mc
bin/htop
bin/gengrub
bin/kernel/6/7
bin/kernel/6/6
bin/dropbear/runit

bin/fixits(delay=10)

set/fs
set/stalix/server
{% endblock %}
