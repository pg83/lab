{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/mirror/unwrap(user=mirror,wd=/home/mirror/,port=8080)
{% endblock %}
