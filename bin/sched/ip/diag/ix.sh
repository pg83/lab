{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
lab/bin/sched/ip/diag/scripts(delay={{delay}})
lab/bin/add/prefix
{% endblock %}
