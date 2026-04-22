{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/xfs/info/scripts(delay={{delay}})
bin/add/prefix
bin/ix/timeout
bin/xfsprogs
{% endblock %}
