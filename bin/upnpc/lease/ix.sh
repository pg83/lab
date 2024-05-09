{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched
bin/upnpc
bin/upnpc/lease/script
{% endblock %}
