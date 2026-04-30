{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/hugepages/scripts(delay={{delay}})
{% endblock %}
