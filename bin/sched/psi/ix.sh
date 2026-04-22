{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/psi/scripts(delay={{delay}})
bin/add/prefix
bin/ix/timeout
{% endblock %}
