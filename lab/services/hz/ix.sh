{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/etc/user(user=hz)
lab/services/hz/runit(srv_dir=hz,srv_user=hz)
{% endblock %}
