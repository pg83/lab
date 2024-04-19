{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
rm -rf /home
mkdir /home
mount /dev/sda /home
mkdir -p /var/mnt/minio/1
mkdir -p /var/mnt/minio/2
mount /dev/sdb /var/mnt/minio/1
mount /dev/sdc /var/mnt/minio/2
{% endblock %}
