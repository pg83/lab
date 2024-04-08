{% extends '//die/hub.sh' %}

{% block run_deps %}
#lab/services/mirror
lab/services/nebula/lh
lab/services/ci(ci_targets=set/ci)
{% endblock %}
