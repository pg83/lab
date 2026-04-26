{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
bin/sched/eth/stat/scripts(delay={{delay}})
bin/ethtool
bin/add/prefix
{% endblock %}
