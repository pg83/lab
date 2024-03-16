{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
lab/services/mirror/rsync
lab/services/ci(ci_targets=set/ci/tier/1)
{% endblock %}
