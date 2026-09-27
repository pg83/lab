{% extends '//die/hub.sh' %}

{# Once per delay: hand this host's puts that never settled to its repair. #}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/s3/scan/scripts(delay={{delay}},host={{host}},config={{config}})
bin/s3/store
{% endblock %}
