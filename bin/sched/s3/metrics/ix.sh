{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/s3/metrics/scripts(delay={{delay}})
bin/python
{% endblock %}
