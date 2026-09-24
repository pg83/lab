{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/runit/1.d

cat << EOF > ${out}/etc/runit/1.d/01-04-cgroup-controllers.sh
# delegate the memory controller down to the per-service cgroups that cg
# creates under /sys/fs/cgroup/srv (the srv level does not exist yet at stage 1)
echo +memory > /sys/fs/cgroup/cgroup.subtree_control
mkdir -p /sys/fs/cgroup/srv
echo +memory > /sys/fs/cgroup/srv/cgroup.subtree_control
EOF
{% endblock %}
