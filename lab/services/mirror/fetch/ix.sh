{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/wget
bin/make
bin/python
lab/services/mirror/fetch/unwrap(user=mirror,wd=/home/mirror/)
{% endblock %}
