{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
btrfs device scan
btrfs device scan /dev/sda /dev/sdb /dev/sdc
sleep 10
btrfs device scan
btrfs device scan /dev/sda /dev/sdb /dev/sdc
mkdir -p /var/mnt/torrent
mount /dev/sda /var/mnt/torrent
{% endblock %}
