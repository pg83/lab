{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/ci(ci_targets=set/ci/tier/1)
{% endblock %}
