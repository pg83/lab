{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/sftp/go
lab/etc/user(user=sftp)
lab/services/sftp/runit(srv_dir=sftp,srv_user=sftp)
{% endblock %}
