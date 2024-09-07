{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
{#
mdadm --assemble md0 /dev/sdb2 /dev/sdc2
mdadm --assemble md1 /dev/md/md0 /dev/sdd2
echo '/dev/sda' > /sys/fs/bcache/register
echo '/dev/md/md1' > /sys/fs/bcache/register
dmesg
bcache attach /dev/sda /dev/md/md1
dmesg
sleep 10
mkdir -p /var/mnt/ci
mount /dev/bcache0 /var/mnt/ci
chown ci:ci /var/mnt/ci
#}
{% endblock %}
