{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
btrfs device scan
mount /dev/sda /home
mkdir /var/mnt/minio/1
mkdir /var/mnt/minio/2
mkdir /var/mnt/minio/3
mount /dev/sdb1 /var/mnt/minio/1
mount /dev/sdb2 /var/mnt/minio/2
mount /dev/sdc1 /var/mnt/minio/3
{% endblock %}
