{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
lab/bin/sched/smart/scripts(delay={{delay}})
lab/bin/add/prefix
bin/smart/mon/tools
{% endblock %}
