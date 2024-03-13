{% extends '//etc/services/runit/script/ix.sh' %}

{% block srv_command %}
export SFTPGO_SFTPD__HOST_KEYS=/etc/keys/ssh_rsa,/etc/keys/ssh_ecdsa,/etc/keys/ssh_ed25519

exec sftpgo portable \
    --directory {{sftp_dir}} \
    --ftpd-port 8001 \
    --password qwerty123 \
    --username anon \
    --sftpd-port 8002
{% endblock %}
