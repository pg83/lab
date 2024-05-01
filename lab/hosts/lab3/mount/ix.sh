{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
mkdir -p /var/mnt/ci
mkdir -p /var/mnt/minio/1
mkdir -p /var/mnt/minio/2
mkdir -p /var/mnt/minio/3
mount LABEL=HOME /var/mnt/ci
mount LABEL=MINIO_1 /var/mnt/minio/1
mount LABEL=MINIO_2 /var/mnt/minio/2
mount LABEL=MINIO_3 /var/mnt/minio/3
rm -rf /home
mkdir /home
{% endblock %}
