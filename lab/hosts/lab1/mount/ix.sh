{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
mkdir -p /var/mnt/minio/1
mkdir -p /var/mnt/minio/2
mkdir -p /var/mnt/minio/3
mount LABEL=MINIO_1 /var/mnt/minio/1
mount LABEL=MINIO_2 /var/mnt/minio/2
mount LABEL=MINIO_3 /var/mnt/minio/3

mdadm --assemble md0 /dev/sdb2 /dev/sdc2
mdadm --assemble md1 /dev/md/md0 /dev/sdd2
echo '/dev/sda' > /sys/fs/bcache/register
echo '/dev/md/md1' > /sys/fs/bcache/register
bcache attach /dev/sda /dev/md/md1
mkdir -p /var/mnt/ci
mount /dev/bcache0 /var/mnt/ci
{% endblock %}
