{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
mkdir -p /var/mnt/home
mkdir -p /var/mnt/minio/1
mkdir -p /var/mnt/minio/2
mount /dev/sda /var/mnt/home
mount /dev/sdb /var/mnt/minio/1
mount /dev/sdc /var/mnt/minio/2
rm -rf /home
ln -s /var/mnt/home /home
{% endblock %}
