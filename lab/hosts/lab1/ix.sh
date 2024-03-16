{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/mirror(mirror_rsync=1)
lab/services/ci(ci_targets=set/ci)
{% endblock %}
