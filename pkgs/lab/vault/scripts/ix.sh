{% extends '//die/proxy.sh' %}

{% block install %}
cd ${out}; mkdir bin; cd bin

cat << EOF > vault_cycle
#!/usr/bin/env sh
set -xue

sleep 5

mkdir -p /root/.ssh /home/root/.ssh

chmod 0700 /root/.ssh
chmod 0700 /home/root/.ssh

cp /etc/sudo/authorized_keys /root/.ssh/
cp /etc/sudo/authorized_keys /home/root/.ssh/
EOF

chmod +x *
{% endblock %}
