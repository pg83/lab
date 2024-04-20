{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
btrfs device scan /dev/sda /dev/sdb /dev/sdc
sleep 10
btrfs device scan /dev/sda /dev/sdb /dev/sdc
mkdir -p /var/mnt/home
mount /dev/sda /var/mnt/home
rm -rf /home
ln -s /var/mnt/home /home
{% endblock %}
