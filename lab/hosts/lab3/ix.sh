{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
#lab/services/mirror
lab/services/nebula/lh(nebula_host=lighthouse1,nebula_port={{cm.ports.nebula_lh}},nebula_iface=nebula0)
lab/services/ci(ci_targets=set/ci)
{% endblock %}
