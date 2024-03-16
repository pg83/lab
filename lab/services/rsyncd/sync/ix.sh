{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/rsync
lab/etc/user
lab/services/rsyncd/sync/sched(rsync_user={{user}})
{% endblock %}
