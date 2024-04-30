{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
mkdir -p /var/mnt/minio/1
mkdir -p /var/mnt/minio/2
mkdir -p /var/mnt/minio/3
mount LABEL=MINIO_1 /var/mnt/minio/1
mount LABEL=MINIO_2 /var/mnt/minio/2
mount LABEL=MINIO_3 /var/mnt/minio/3
btrfs device scan /dev/sda /dev/sdb /dev/sdc
sleep 10
btrfs device scan /dev/sda /dev/sdb /dev/sdc
mkdir -p /var/mnt/home
mount /dev/sda /var/mnt/home
rm -rf /home
ln -s /var/mnt/home /home
{% endblock %}
