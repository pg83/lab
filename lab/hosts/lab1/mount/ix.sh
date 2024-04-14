{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
rm -rf /home
mkdir /home
mount /dev/sda1 /home
mkdir -p /var/mnt/minio/1
mkdir -p /var/mnt/minio/2
mkdir -p /var/mnt/minio/3
mount /dev/sdb1 /var/mnt/minio/1
mount /dev/sdb2 /var/mnt/minio/2
mount /dev/sdc1 /var/mnt/minio/3
{% endblock %}
