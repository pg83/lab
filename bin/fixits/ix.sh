{% extends '//die/proxy.sh' %}

{% block run_deps %}
bin/sched(delay={{delay}})
{% endblock %}

{% block install %}
cd ${out}; mkdir -p etc/sched/{{delay}}; cd etc/sched/{{delay}}

cat << EOF > fixits.sh
set -x
mkdir -p /ix/trash
chmod 01777 /ix/trash
chmod 01777 /ix/realm
chown -h ix:ix /ix/realm/system
chown -h ix:ix /ix/realm/boot
EOF
{% endblock %}
