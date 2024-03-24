{% extends '//etc/services/runit/script/ix.sh' %}

{% block srv_command %}
set -xue

mkdir -p /home/root/.ssh
chmod 0700 /home/root/.ssh

cp /etc/sudo/authorized_keys /home/root/.ssh/

exec /bin/dropbear \
    -s -e -E -F -P pid \
    -r /etc/keys/dss   \
    -r /etc/keys/rsa   \
    -r /etc/keys/ecdsa \
    -r /etc/keys/ed25519
{% endblock %}
