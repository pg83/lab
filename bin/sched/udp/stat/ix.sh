{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/udp/stat/scripts(delay={{delay}})
bin/add/prefix
{% endblock %}
