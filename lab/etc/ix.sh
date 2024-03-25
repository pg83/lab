{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/etc/env
lab/etc/keys
lab/etc/hosts
{% for d in (cluster_map | des).by_host[hostname].get('disabled', []) %}
lab/etc/stopper(srv_dir={{d}})
{% endfor %}
{% endblock %}
