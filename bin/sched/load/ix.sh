{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
lab/bin/sched/load/scripts(delay={{delay}})
lab/bin/add/prefix
{% endblock %}
