{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/proc/cpu/scripts(delay={{delay}})
bin/add/prefix
{% endblock %}
