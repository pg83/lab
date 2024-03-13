{% extends '//etc/services/runit/script/ix.sh' %}

{% block srv_user_prepare %}
{{super()}}
cp /etc/keys/ssh_rsa /var/run/{{srv_dir}}/id_rsa
cp /etc/keys/ssh_ecdsa /var/run/{{srv_dir}}/id_ecdsa
cp /etc/keys/ssh_ed25519 /var/run/{{srv_dir}}/id_ed25519
chown {{srv_user}} /var/run/{{srv_dir}}/id_*
{% endblock %}

{% block srv_command %}
exec sftpgo portable \
    --directory {{sftp_dir}} \
    --ftpd-port 8001 \
    --password qwerty123 \
    --username anon \
    --sftpd-port 8002
{% endblock %}
