{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/ip/diag/scripts(delay={{delay}})
bin/add/prefix
{% endblock %}
