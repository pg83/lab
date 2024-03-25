{% extends '//die/proxy.sh' %}

{% block install %}
mkdir -p ${out}/etc/runit/1.d

cat << EOF > ${out}/etc/runit/1.d/20-mount-rw.sh
# mount extra fs
btrfs device scan /dev/sda /dev/sdb
mount /dev/sda /home
EOF
{% endblock %}
