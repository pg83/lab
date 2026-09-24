{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/runit/1.d

cat << EOF > ${out}/etc/runit/1.d/01-04-cgroup-controllers.sh
# delegate the memory controller to the service cgroups under /sys/fs/cgroup/srv
echo +memory > /sys/fs/cgroup/cgroup.subtree_control
EOF
{% endblock %}
