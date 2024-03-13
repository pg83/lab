{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sftp/go
etc/user/nologin(userid=1005,user=sftp)
lab/services/sftp/runit(srv_dir=sftp,srv_user=sftp)
{% endblock %}
