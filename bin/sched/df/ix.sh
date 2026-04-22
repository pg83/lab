{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/df/scripts(delay={{delay}})
bin/add/prefix
bin/ix/timeout
{% endblock %}
