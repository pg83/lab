{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/smart/scripts(delay={{delay}})
bin/python
bin/smart/mon/tools
{% endblock %}
