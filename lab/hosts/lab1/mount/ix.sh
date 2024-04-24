{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
#mkdir -p /var/mnt/home
mkdir -p /var/mnt/minio/1
mkdir -p /var/mnt/minio/2
mkdir -p /var/mnt/minio/3
mount LABEL=HOME /var/mnt/home
mount LABEL=MINIO_1 /var/mnt/minio/1
mount LABEL=MINIO_2 /var/mnt/minio/2
mount LABEL=MINIO_3 /var/mnt/minio/3
mkdir -p /home
#rm -rf /home
#ln -s /var/mnt/home /home
{% endblock %}
