{% extends '//die/hub.sh' %}

{% set cm = cluster_map | des %}

{% block run_deps %}
bin/iperf
etc/user/nobody
etc/services/runit(srv_dir=iperf,srv_command exec iperf -s -p {{cm.ports.iperf}},srv_user=nobody)
{% endblock %}
