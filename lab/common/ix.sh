{% extends '//die/hub.sh' %}

{% block run_deps %}
{{(cluster_map | des).by_host[hostname].extra}}

lab/etc

lab/services/autoupdate(user=ix)

bin/mc
bin/htop
bin/gengrub
etc/host/keys
bin/kernel/6/8
bin/kernel/6/7
bin/fixits(delay=10)

set/fs
set/stalix/server
{% endblock %}
