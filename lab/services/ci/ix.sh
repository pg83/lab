{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/ci/unwrap(user=ci,wd=/home/ci)
{% endblock %}
