{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
bin/iperf/3
etc/user/nobody
etc/services/runit(srv_dir=iperf,srv_command exec iperf3 -s -p {{cm.ports.iperf}},srv_user=nobody)
{% endblock %}
