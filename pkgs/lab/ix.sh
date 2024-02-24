{% extends '//die/hub.sh' %}

{% block run_deps %}
set/stalix
bin/kernel/6/7
bin/kernel/6/6
bin/kernel/gengrub
lab/autoupdate(user=ix)
{% endblock %}
