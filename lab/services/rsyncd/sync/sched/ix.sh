{% extends '//die/proxy.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
{% endblock %}

{% block install %}
cd ${out}; mkdir -p etc/sched/{{delay}}; cd etc/sched/{{delay}}

cat << EOF > sync.sh
set -xue
mkdir -p {{rsync_where}}
chown {{rsync_user}} {{rsync_where}}
cd {{rsync_where}}
rsync --ignore-existing -P -r {{rsync_share}} .
EOF
{% endblock %}
