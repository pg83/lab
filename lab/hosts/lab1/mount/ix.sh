{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
mkdir -p /var/mnt/home
mkdir -p /var/mnt/minio/1
mkdir -p /var/mnt/minio/2
mkdir -p /var/mnt/minio/3
mount /dev/sda1 /var/mnt/home
mount /dev/sdb1 /var/mnt/minio/1
mount /dev/sdb2 /var/mnt/minio/2
mount /dev/sdc1 /var/mnt/minio/3
rm -rf /home
ln -s /var/mnt/home /home
{% endblock %}
