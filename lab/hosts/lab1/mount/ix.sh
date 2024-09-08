{% extends '//die/proxy.sh' %}

{% block install %}
mkdir ${out}/bin

cat << EOF > ${out}/bin/mount_ci
#!/usr/bin/env sh
set -xue
devlink
mdadm --assemble md0 /dev/links/6ce93586-ad55-4248-bb21-d23eac83dbff /dev/links/7965901e-abed-4628-92f2-a1a4194e6d1c
devlink
mdadm --assemble md1 /dev/md/md0 /dev/links/40a63ab3-62f3-43dd-843f-fbed27622bf2
echo '/dev/sda' > /sys/fs/bcache/register
echo '/dev/md/md1' > /sys/fs/bcache/register
bcache attach /dev/sda /dev/md/md1
devlink
mkdir -p \${1}
mount /dev/bcache0 \${1}
chown ci:ci \${1}
EOF

chmod +x ${out}/bin/*
{% endblock %}
