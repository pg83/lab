{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
mkdir -p /var/mnt/home
mkdir -p /var/mnt/minio/1
mkdir -p /var/mnt/minio/2
mount LABEL=HOME /var/mnt/home
mount LABEL=MINIO_1 /var/mnt/minio/1
mount LABEL=MINIO_2 /var/mnt/minio/2
rm -rf /home
ln -s /var/mnt/home /home
{% endblock %}
