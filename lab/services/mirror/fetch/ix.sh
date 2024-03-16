{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/mirror/fetch/unwrap(user=mirror,wd=/home/mirror/)
{% endblock %}
