{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/mc
set/stalix
bin/kernel/6/7
bin/kernel/6/6
bin/kernel/gengrub
lab/services/collector
{% endblock %}
