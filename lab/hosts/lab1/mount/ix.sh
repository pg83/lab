{% extends '//die/hub.sh' %}

{% block install %}
mkdir ${out}/bin

cat << EOF > ${out}/bin/mount_ci
set -xue
mdadm --assemble md0 /dev/sdb2 /dev/sdc2
mdadm --assemble md1 /dev/md/md0 /dev/sdd2
echo '/dev/sda' > /sys/fs/bcache/register
echo '/dev/md/md1' > /sys/fs/bcache/register
bcache attach /dev/sda /dev/md/md1
mkdir -p \${1}
mount /dev/bcache0 \${1}
chown ci:ci \${1}
EOF

chmod +x ${out}/bin/*
{% endblock %}
