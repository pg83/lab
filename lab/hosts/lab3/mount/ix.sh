{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
mkdir -p /var/mnt/minio/1
mkdir -p /var/mnt/minio/2
mount /dev/sda /var/mnt/minio/1
mount /dev/sdb /var/mnt/minio/2
{% endblock %}
