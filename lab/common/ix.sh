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
lab/services/git/evque(evlog_user=git_lab,evlog_url=https://smee.io/ytBWlUqSG8YIRzh)

bin/mc
bin/htop
bin/kernel/6/7
bin/kernel/6/6
bin/kernel/gengrub
bin/dropbear/runit

set/stalix/server
{% endblock %}
