{% extends '//die/hub.sh' %}

{% block run_deps %}
#lab/services/mirror
lab/services/nebula/lh(nebula_host=lighthouse1)
lab/services/ci(ci_targets=set/ci)
{% endblock %}
