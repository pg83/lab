{% extends '//etc/services/runit/script/ix.sh' %}

{% block srv_command %}
exec etcdctl lock hz -- /bin/sh ${PWD}/locked
{% endblock %}

{% block install %}
{{super()}}
cat << EOF > locked
sleep 60
date | etcdctl put /git/logs/git_ci
sleep 60
date | etcdctl put /git/logs/git_lab
EOF
{% endblock %}
