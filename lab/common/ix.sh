{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/mc
lab/etc
set/stalix
bin/kernel/6/7
bin/kernel/6/6
lab/services/ssh
lab/services/etcd
bin/kernel/gengrub
lab/services/collector
lab/services/autoupdate(user=ix)
{% endblock %}
