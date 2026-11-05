{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/sched/{{delay}}

cat << 'EOF' > ${out}/etc/sched/{{delay}}/{{etcd_name}}-snapshot.sh
#!/bin/sh
# The member of {{etcd_name}} on this host, zstd'ed, as one file on its own
# partition {{etcd_part}} next to the data. The partition is mounted in a
# namespace of its own, as {{etcd_name}} mounts it in its.
set -eu

for disk in /dev/sd?; do
    n=$(sgdisk -p ${disk} 2>/dev/null | awk '$NF == "{{etcd_part}}" {print $1}')

    if [ -n "${n}" ]; then
        dev=${disk}${n}
    fi
done

mkdir -p /var/mnt/{{etcd_name}}

exec timeout -s KILL 600s unshare -m sh -eu -c "
mount -t xfs ${dev} /var/mnt/{{etcd_name}}
cd /var/mnt/{{etcd_name}}
ETCDCTL_ENDPOINTS=http://127.0.0.1:{{etcd_port}} nice -n 19 etcdctl snapshot save snapshot.db > /dev/null
nice -n 19 zstd -q -f -T0 --rm snapshot.db -o snapshot.db.zst.tmp
sync -f snapshot.db.zst.tmp
mv snapshot.db.zst.tmp snapshot.db.zst
sync -f snapshot.db.zst
"
EOF

chmod +x ${out}/etc/sched/{{delay}}/{{etcd_name}}-snapshot.sh
{% endblock %}
