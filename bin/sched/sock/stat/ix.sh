{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
lab/bin/sched/sock/stat/scripts(delay={{delay}})
lab/bin/add/prefix
{% endblock %}
