{% extends '//die/c/autorehell.sh' %}

{% block pkg_name %}
iperf
{% endblock %}

{% block version %}
3.20
{% endblock %}

{% block fetch %}
https://github.com/esnet/iperf/archive/refs/tags/{{self.version().strip()}}.tar.gz
84640ea0f43831850434e50134d0554b7a94f97fb02e2488ffbe252c9fb05a56
{% endblock %}

{% block bld_libs %}
lib/c
{% endblock %}

{% block conf_ver %}
2/71
{% endblock %}

{% block patch %}
{{super()}}
# Force 1MB pthread stack; musl's ~80KB default overflows iperf3 workers.
sed -i 's|if (pthread_create(&(sp->thr), &attr,|pthread_attr_setstacksize(\&attr, 1 << 20); if (pthread_create(\&(sp->thr), \&attr,|' src/iperf_server_api.c src/iperf_client_api.c
{% endblock %}
