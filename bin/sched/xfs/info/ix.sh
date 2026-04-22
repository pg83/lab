{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
lab/bin/sched/xfs/info/scripts(delay={{delay}})
lab/bin/add/prefix
bin/xfsprogs
{% endblock %}
