{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/mirror/rsync
lab/services/ci(ci_targets=set/ci)
{% endblock %}
