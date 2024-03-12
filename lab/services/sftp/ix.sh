{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sftp/go
etc/user/nologin(userid=1005,user=sftp)
etc/services/runit(srv_dir=sftp,srv_user=sftp,srv_command=exec sftpgo portable --directory {{sftp_dir}} --ftpd-port 8001 --password qwerty123 --username anon --sftpd-port 8002)
{% endblock %}
